from __future__ import annotations

from cfg.schema import AppConfig
from llm.mock import MockLLMClient
from llm.mock_scenarios import planner_mock, reviewer_mock, executor_mock, \
  default_mock
from llm.openai_client import OpenAICompatibleClient
from llm.protocol import LLMClient


# LLMClient factory
def create_llm(*, env: str, app_cfg: AppConfig) -> LLMClient:
  cfg = app_cfg.llm

  if env == "test" or cfg.provider == "mock":
    return MockLLMClient(
      planner=planner_mock,
      reviewer=reviewer_mock,
      executor=executor_mock,
      default=default_mock,
    )

  if cfg.provider == "openai":
    if not cfg.base_url:
      raise ValueError("app.yaml: llm.base_url is required for provider=openai")

    return OpenAICompatibleClient(base_url=cfg.base_url)

  raise ValueError(f"Unsupported llm.provider: {cfg.provider}")