# Plan: Critic Integration into Orchestrator

## Context

The system already has:
- `CriticResult` / `CriticIssue` models in `orchestrator/models.py`
- Critic prompts in `prompts/critic/system.md` and `prompts/critic/user.md`
- `"critic"` role in `cfg/schema.py` and all `config/*/models.yaml`
- Standalone CLI command `cli/commands/review_step.py` (not OOP, calls LLM directly)
- `Orchestrator.__init__` intentionally excludes critic ("no critic loop" — comment in `orchestrator.py`)

What is missing: a `Critic` class, its wiring in `build_orchestrator.py`, and the retry loop in `Orchestrator.run()`.

User confirmed: critic should be integrated into `Orchestrator.run()` with a retry loop.
On rejection: same executor re-runs the step with critic issues passed as feedback.

---

## Files to change

### 1. CREATE `orchestrator/critic.py`

Mirrors `planner.py` pattern: thin wrapper around LLMClient.

```python
class Critic:
    def __init__(self, *, llm: LLMClient, model: str, system_prompt: str, user_template: str): ...
    async def review(self, step: PlanStep, result: StepResult) -> CriticResult: ...
```

- Renders user prompt via `render_critic_template(step, result, user_template)` (new renderer fn)
- Strips markdown fences from response with `_extract_json` (same logic as in planner.py)
- Validates response via `CriticResult.model_validate_json()`

---

### 2. MODIFY `orchestrator/prompting/renderer.py`

Two additions:

**a) Extend `render_step_template` with an optional `critic_feedback` param:**
```python
def render_step_template(step, template, previous_results="", critic_feedback="") -> str:
    values = {
        ...existing keys...,
        "CRITIC_FEEDBACK": critic_feedback,
    }
```

**b) Add `render_critic_template(step, result, template) -> str`:**
- Matches variables in `prompts/critic/user.md`: `STEP`, `STEP_RESULT`, `SUCCESS_CRITERIA`
- Reuses existing `render_template` utility from `tools.prompt`

---

### 3. MODIFY `orchestrator/executors/base.py`

Add `critic_feedback: str = ""` to `execute()` abstract signature:
```python
@abstractmethod
async def execute(self, step: PlanStep, previous_results: str = "", critic_feedback: str = "") -> StepResult:
```

---

### 4. MODIFY `orchestrator/executors/generic.py` and `code.py`

Both executors: forward `critic_feedback` to `render_step_template`. No other changes.

---

### 5. MODIFY `prompts/generic_executor/user.md` and `prompts/code_executor/user.md`

Add optional critic feedback block after `<previous_results>`:
```xml
<critic_feedback>
{{CRITIC_FEEDBACK}}
</critic_feedback>
```

Block is rendered as empty string when not retrying, so no behavior change on first attempt.

---

### 6. MODIFY `orchestrator/orchestrator.py`

**Constructor changes:**
```python
def __init__(
    self,
    *,
    planner: Planner,
    executors: Dict[str, BaseExecutor],
    router: ExecutorRouter,
    critic: Critic | None = None,
    max_retries: int = 1,
):
```

**`run()` change:**  
Replace `_execute_step(step, ...)` call with `_execute_with_review(step, ...)`.

**Add `_execute_with_review()`:**
```python
async def _execute_with_review(
    self, step: PlanStep, previous_results: List[StepResult]
) -> StepResult:
    critic_feedback = ""
    for attempt in range(self._max_retries + 1):
        result = await self._execute_step(step, previous_results, critic_feedback)
        if self._critic is None:
            return result
        verdict = await self._critic.review(step, result)
        if verdict.approved:
            return result
        if attempt < self._max_retries:
            critic_feedback = _format_feedback(verdict)  # see below
        else:
            log.warning("Critic rejected step %d after %d retries", step.id, attempt)
            return result  # return best-effort result
    return result
```

**Add `_format_feedback(verdict: CriticResult) -> str`** (module-level helper):  
Formats issues as a compact text block to inject into `CRITIC_FEEDBACK`.

---

### 7. MODIFY `orchestrator/build_orchestrator.py`

```python
from orchestrator.critic import Critic

critic_model = models_registry.models["critic"].primary
critic_system_prompt, critic_user_template = load_role_prompts("critic", prompts_dir=app_cfg.prompts_dir)

critic = Critic(
    llm=llm,
    model=critic_model,
    system_prompt=critic_system_prompt,
    user_template=critic_user_template,
)

return Orchestrator(
    planner=planner,
    executors=executors,
    router=router,
    critic=critic,
)
```

---

## Tests to add

- `tests/orchestrator/test_critic.py`: unit test `Critic.review()` with mock LLM
  - approved path (returns `CriticResult(approved=True, ...)`)
  - rejection path (returns `CriticResult(approved=False, issues=[...], ...)`)
- `tests/orchestrator/test_orchestrator_with_critic.py`: integration test with mock executor + mock critic
  - step approved on first attempt — no retry
  - step rejected once then approved — retry with feedback
  - step rejected all retries — returns last result with warning logged

---

## Verification

```bash
# Run tests (mock env, no network)
uv run pytest -q

# Smoke test end-to-end with real LLM (prod)
advisor --env prod plan "Create a 2-step plan to summarize the planner–critic architecture."
```