from __future__ import annotations

from typing import Callable, Optional

from llm.types import ChatRequest, ChatResponse


MockScenario = Callable[[ChatRequest], ChatResponse]


class MockLLMClient:
  """
  Pre-Orchestrator mock LLM client.

  Contract:
  - No routing
  - No role inference
  - No meta usage
  - Executes exactly one injected behavior
  """

  def __init__(
      self,
      *,
      planner: Optional[MockScenario] = None,
      critic: Optional[MockScenario] = None,
      default: Optional[MockScenario] = None,
  ):
    self._planner = planner
    self._critic = critic
    self._default = default

  async def chat(self, req: ChatRequest) -> ChatResponse:
    """
    IMPORTANT:
    This layer does NOT decide behavior.

    In pre-Orchestrator stage, the caller MUST NOT rely on this method.
    """

    raise RuntimeError(
      "MockLLMClient.chat() is disabled in pre-Orchestrator design. "
      "Use role-specific factory clients instead."
    )