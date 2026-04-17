from __future__ import annotations

from cfg.schema import AppConfig
from llm.openai_client import OpenAICompatibleClient
from llm.protocol import LLMClient
from llm.mock_scenarios import (
  planner_mock,
  critic_mock,
  default_mock,
)


# -------------------------
# Test-specific clients
# -------------------------
def create_test_planner_llm() -> LLMClient:
  """
  Used ONLY for CLI: plan
  """
  return _PlannerMockClient(planner_mock)


def create_test_critic_llm() -> LLMClient:
  """
  Used ONLY for CLI: review-step
  """
  return _CriticMockClient(critic_mock)


# -------------------------
# Production factory
# -------------------------
def create_llm(*, env: str, app_cfg: AppConfig) -> LLMClient:
  cfg = app_cfg.llm

  if env == "test" or cfg.provider == "mock":
    # default safe fallback (not used for role routing)
    return _PlannerMockClient(planner_mock)

  if cfg.provider == "openai":
    if not cfg.base_url:
      raise ValueError("app.yaml: llm.base_url is required for provider=openai")

    return OpenAICompatibleClient(base_url=cfg.base_url)

  raise ValueError(f"Unsupported llm.provider: {cfg.provider}")


# -------------------------
# Internal minimal clients
# -------------------------
class _PlannerMockClient:
  def __init__(self, fn):
    self._fn = fn

  async def chat(self, req):
    return self._fn(req)


class _CriticMockClient:
  def __init__(self, fn):
    self._fn = fn

  async def chat(self, req):
    return self._fn(req)