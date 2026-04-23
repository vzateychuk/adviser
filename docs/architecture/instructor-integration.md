# Instructor Integration Architecture

## Overview

This document describes the integration of [instructor](https://github.com/jxnl/instructor)
for structured LLM outputs in the PEC (Plan-Execute-Critic) pipeline.

## Design Principles

1. **Vendor Agnosticism**: Business logic (Planner, Executor, Critic) never imports
   SDK-specific code. All vendor details are encapsulated in `llm/` adapters.

2. **Protocol-Driven**: The `LLMClient` protocol defines the contract. Any adapter
   (OpenAI, Anthropic, Mock) implements this protocol.

3. **Type Safety**: Structured outputs use Pydantic models as response schemas.
   Validation happens at the adapter layer, not in business logic.

4. **Graceful Degradation**: Legacy `chat()` method preserved for backward
   compatibility and free-form generation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BUSINESS LOGIC LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Planner                                                         │   │
│  │  • Calls llm.chat_structured(req, PlannerOutputSchema)          │   │
│  │  • Receives validated Pydantic model                            │   │
│  │  • No JSON/YAML parsing                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Critic                                                          │   │
│  │  • Calls llm.chat_structured(req, CriticResult)                 │   │
│  │  • Receives approved/issues directly                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PROTOCOL LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  LLMClient (Protocol)                                            │   │
│  │  • chat(req) -> ChatResponse                                     │   │
│  │  • chat_structured(req, response_model, max_retries) -> T        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ADAPTER LAYER                                    │
│  ┌────────────────────────────┐    ┌────────────────────────┐          │
│  │ OpenAICompatibleClient     │    │ MockLLMClient          │          │
│  │ • instructor.from_openai() │    │ • Pre-built Pydantic   │          │
│  │ • Mode.JSON for compat     │    │   objects for tests    │          │
│  │ • Retry with feedback      │    │ • No network calls     │          │
│  └────────────────────────────┘    └────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

## LLMClient Protocol

```python
class LLMClient(Protocol):
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Legacy unstructured text completion."""
        ...

    async def chat_structured(
        self,
        req: ChatRequest,
        response_model: type[T],
        *,
        max_retries: int = 2,
    ) -> T:
        """Structured completion with Pydantic validation."""
        ...
```

## Structured Output Schema Design

### Best Practices for `Field(description=...)`

Descriptions are injected into the JSON schema by instructor, improving LLM compliance:

```python
class PlannerOutputSchema(BaseModel):
    action: Literal["PLAN", "SKIP"] = Field(
        description=(
            "PLAN if the document should be processed, "
            "SKIP if it's not a medical document"
        ),
    )
    schema_name: str | None = Field(
        description=(
            "Target schema ID from catalog (e.g., 'lab', 'consultation'). "
            "Required when action=PLAN, null when action=SKIP"
        ),
    )
```

### Recommendations

1. **Be explicit about constraints**: "Required when X", "Must be one of [A, B, C]"
2. **Give examples**: "e.g., 'lab', 'consultation'"
3. **Explain relationships**: "null when action=SKIP"
4. **Keep descriptions concise**: LLMs have limited context

## Error Handling

### Error Hierarchy

```
LLMError (base)
├── StructuredOutputError
│   ├── raw_response: str | None
│   ├── validation_errors: list[dict]
│   └── attempts: int
```

### Handling in Orchestrator

```python
from llm.errors import LLMError, StructuredOutputError

try:
    plan = await planner.plan(user_request=..., document_content=...)
except StructuredOutputError as e:
    # Validation failed after retries
    log.error("Planner output invalid: %s", e.validation_errors)
    context.status = RunStatus.FAILED
    # Option 1: Retry with different prompt
    # Option 2: Fall back to unstructured parsing
    # Option 3: Fail the run
except LLMError as e:
    # Transport error (timeout, rate limit, etc.)
    log.error("LLM call failed: %s (status=%s)", e, e.status_code)
    raise
```

### Instructor Retry Behavior

Instructor handles retries internally:

1. First attempt: Send prompt + JSON schema
2. On validation failure: Inject error message into prompt, retry
3. After `max_retries`: Raise `ValidationError` (caught as `StructuredOutputError`)

## Mock Testing

For tests, use `StructuredMockScenario` to return pre-built Pydantic objects:

```python
def planner_structured_mock(req: ChatRequest, response_model: type[T]) -> T:
    from flows.pec.planner import PlannerOutputSchema, PlanStepSchema
    
    return PlannerOutputSchema(
        action="PLAN",
        goal="Extract medical data",
        schema_name="lab",
        steps=[PlanStepSchema(id=1, title="Extract", ...)],
    )
```

This bypasses all parsing and validation, making tests fast and deterministic.

## Migration Checklist

- [x] Add `instructor>=1.7.0` to dependencies
- [x] Extend `LLMClient` protocol with `chat_structured()`
- [x] Update `OpenAICompatibleClient` with instructor integration
- [x] Update `MockLLMClient` with structured scenarios
- [x] Add `StructuredOutputError` to error hierarchy
- [x] Refactor `Planner` to use `chat_structured()`
- [x] Create `PlannerOutputSchema` with optimized descriptions
- [x] Update mock scenarios for structured output
- [ ] Refactor `Critic` to use `chat_structured()`
- [ ] Refactor `OcrExecutor` to use `chat_structured()` (if applicable)
- [ ] Add integration tests for structured output flow

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `instructor>=1.7.0` |
| `llm/protocol.py` | Added `chat_structured()` method |
| `llm/errors.py` | Added `StructuredOutputError` |
| `llm/openai_client.py` | Instructor integration |
| `llm/mock.py` | Structured scenario support |
| `llm/mock_scenarios.py` | Added structured mock scenarios |
| `llm/factory.py` | Wire structured scenarios |
| `flows/pec/planner.py` | Full refactor to structured outputs |
| `flows/pec/models.py` | Added Field descriptions |
| `flows/pec/build_pec.py` | Pass max_retries to Planner |
