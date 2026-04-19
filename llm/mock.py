from __future__ import annotations

from typing import Callable, Optional

from llm.types import ChatRequest, ChatResponse


MockScenario = Callable[[ChatRequest], ChatResponse]


class MockLLMClient:
  def __init__(
      self,
      *,
      planner: MockScenario | None = None,
      critic: MockScenario | None = None,
      executor: MockScenario | None = None,   # добавить
      default: MockScenario | None = None,
  ):
    self._planner = planner
    self._critic = critic
    self._executor = executor
    self._default = default

  async def chat(self, req: ChatRequest) -> ChatResponse:
    scenario = self._resolve_scenario(req)
    if scenario is None:
      raise RuntimeError(f"No matching scenario for request. Set a default mock.")
    return scenario(req)

  def _resolve_scenario(self, req: ChatRequest) -> MockScenario | None:
    system = next(
      (m.content for m in req.messages if m.role == "system"), ""
    )
    if "Role: Planner" in system:
      return self._planner or self._default
    if "Role: Critic" in system:
      return self._critic or self._default
    return self._executor or self._default