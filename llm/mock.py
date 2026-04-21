from __future__ import annotations

from typing import Callable, Optional

from llm.types import ChatRequest, ChatResponse


MockScenario = Callable[[ChatRequest], ChatResponse]


class MockLLMClient:
    """
    Mock LLM client for tests.

    Routes requests to the appropriate MockScenario by inspecting the system
    prompt for a role identifier string:
      "Role: Planner"      -> planner scenario
      "Role: OcrExecutor"  -> ocr_executor scenario
      "Role: Critic"       -> critic scenario
      (no match)           -> default scenario
    """

    def __init__(
        self,
        *,
        planner: MockScenario | None = None,
        ocr_executor: MockScenario | None = None,
        critic: MockScenario | None = None,
        default: MockScenario | None = None,
    ):
        self._planner = planner
        self._ocr_executor = ocr_executor
        self._critic = critic
        self._default = default

    async def chat(self, req: ChatRequest) -> ChatResponse:
        scenario = self._resolve_scenario(req)
        if scenario is None:
            raise RuntimeError("No matching mock scenario. Set a default mock or the relevant role scenario.")
        return scenario(req)

    def _resolve_scenario(self, req: ChatRequest) -> MockScenario | None:
        system = next(
            (m.content for m in req.messages if m.role == "system"), ""
        )
        if "Role: Planner" in system:
            return self._planner or self._default
        if "Role: OcrExecutor" in system:
            return self._ocr_executor or self._default
        if "Role: Critic" in system:
            return self._critic or self._default
        return self._default