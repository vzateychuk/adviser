from __future__ import annotations

import logging
from typing import Callable

from llm.types import ChatRequest, ChatResponse

log = logging.getLogger(__name__)


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
        model_alias: str,
        planner: MockScenario | None = None,
        ocr_executor: MockScenario | None = None,
        critic: MockScenario | None = None,
        default: MockScenario | None = None,
    ):
        self._model_alias = model_alias
        self._planner = planner
        self._ocr_executor = ocr_executor
        self._critic = critic
        self._default = default

    async def chat(self, req: ChatRequest) -> ChatResponse:
        scenario = self._resolve_scenario(req)
        if scenario is None:
            raise RuntimeError("No matching mock scenario. Set a default mock or the relevant role scenario.")
        log.debug("MockLLMClient.chat(model_alias=%s)", self._model_alias)
        resp = scenario(req)
        if not resp.model_alias:
            return resp.model_copy(update={"model_alias": self._model_alias})
        return resp

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