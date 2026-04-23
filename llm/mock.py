from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from llm.errors import StructuredOutputError
from llm.types import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Legacy text-based scenario (for backward compatibility)
MockScenario = Callable[[ChatRequest], ChatResponse]

# New structured scenario: returns a Pydantic model directly
StructuredMockScenario = Callable[[ChatRequest, type[T]], T]


class MockLLMClient:
    """Mock LLM client for tests with structured output support.

    Routes requests to the appropriate MockScenario by inspecting the system
    prompt for a role identifier string:
      "Role: Planner"      -> planner scenario
      "Role: OcrExecutor"  -> ocr_executor scenario
      "Role: Critic"       -> critic scenario
      (no match)           -> default scenario

    For structured outputs (chat_structured), the mock scenarios receive the
    response_model type and return a pre-built Pydantic instance directly,
    bypassing all JSON/YAML parsing. This makes tests deterministic and fast.
    """

    def __init__(
        self,
        *,
        model_alias: str,
        # Legacy text scenarios
        planner: MockScenario | None = None,
        ocr_executor: MockScenario | None = None,
        critic: MockScenario | None = None,
        default: MockScenario | None = None,
        # Structured output scenarios (take precedence when using chat_structured)
        planner_structured: StructuredMockScenario[Any] | None = None,
        ocr_executor_structured: StructuredMockScenario[Any] | None = None,
        critic_structured: StructuredMockScenario[Any] | None = None,
        default_structured: StructuredMockScenario[Any] | None = None,
    ):
        self._model_alias = model_alias

        # Legacy text scenarios
        self._planner = planner
        self._ocr_executor = ocr_executor
        self._critic = critic
        self._default = default

        # Structured scenarios
        self._planner_structured = planner_structured
        self._ocr_executor_structured = ocr_executor_structured
        self._critic_structured = critic_structured
        self._default_structured = default_structured

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Legacy text completion for backward compatibility."""
        scenario = self._resolve_text_scenario(req)
        if scenario is None:
            raise RuntimeError("No matching mock scenario. Set a default mock or the relevant role scenario.")
        log.debug("MockLLMClient.chat(model_alias=%s)", self._model_alias)
        resp = scenario(req)
        if not resp.model_alias:
            return resp.model_copy(update={"model_alias": self._model_alias})
        return resp

    async def chat_structured(
        self,
        req: ChatRequest,
        response_model: type[T],
        *,
        max_retries: int = 2,
    ) -> T:
        """Return a pre-built Pydantic model for structured output tests.

        The scenario function receives the response_model type so it can
        construct the appropriate mock response. This allows testing the
        full pipeline without LLM calls.
        """
        scenario = self._resolve_structured_scenario(req)

        if scenario is None:
            # Fallback: try legacy text scenario and parse as JSON
            text_scenario = self._resolve_text_scenario(req)
            if text_scenario is not None:
                log.debug(
                    "MockLLMClient.chat_structured falling back to text scenario for %s",
                    response_model.__name__,
                )
                resp = text_scenario(req)
                try:
                    return response_model.model_validate_json(resp.text)
                except Exception as e:
                    raise StructuredOutputError(
                        f"Mock text scenario output is not valid {response_model.__name__}",
                        raw_response=resp.text,
                        validation_errors=[{"msg": str(e)}],
                    ) from e

            raise RuntimeError(
                f"No matching mock scenario for {response_model.__name__}. "
                "Set a structured or default scenario."
            )

        log.debug(
            "MockLLMClient.chat_structured(model_alias=%s, response_model=%s)",
            self._model_alias,
            response_model.__name__,
        )
        return scenario(req, response_model)

    def _resolve_text_scenario(self, req: ChatRequest) -> MockScenario | None:
        """Route to legacy text scenario by system prompt role marker."""
        role = self._detect_role(req)
        scenarios = {
            "planner": self._planner,
            "ocr_executor": self._ocr_executor,
            "critic": self._critic,
        }
        return scenarios.get(role) or self._default

    def _resolve_structured_scenario(self, req: ChatRequest) -> StructuredMockScenario[Any] | None:
        """Route to structured scenario by system prompt role marker."""
        role = self._detect_role(req)
        scenarios = {
            "planner": self._planner_structured,
            "ocr_executor": self._ocr_executor_structured,
            "critic": self._critic_structured,
        }
        return scenarios.get(role) or self._default_structured

    def _detect_role(self, req: ChatRequest) -> str:
        """Extract role from system prompt markers."""
        system = next((m.content for m in req.messages if m.role == "system"), "")
        if "Role: Planner" in system:
            return "planner"
        if "Role: OcrExecutor" in system:
            return "ocr_executor"
        if "Role: Critic" in system:
            return "critic"
        return "default"
