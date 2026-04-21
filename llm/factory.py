from __future__ import annotations

from cfg.schema import AppConfig
from llm.mock import MockLLMClient
from llm.openai_client import OpenAICompatibleClient
from llm.protocol import LLMClient
from llm.mock_scenarios import (
    critic_mock,
    default_mock,
    ocr_executor_mock,
    planner_mock,
)


def create_llm(*, env: str, app_cfg: AppConfig) -> LLMClient:
    """
    LLM client factory.

    test / mock  -> MockLLMClient with role-based routing (no network)
    openai       -> OpenAICompatibleClient (LiteLLM proxy or OpenAI)
    """
    cfg = app_cfg.llm

    if env == "test" or cfg.provider == "mock":
        return MockLLMClient(
            planner=planner_mock,
            ocr_executor=ocr_executor_mock,
            critic=critic_mock,
            default=default_mock,
        )

    if cfg.provider == "openai":
        if not cfg.base_url:
            raise ValueError("app.yaml: llm.base_url is required for provider=openai")
        return OpenAICompatibleClient(base_url=cfg.base_url)

    raise ValueError(f"Unsupported llm.provider: {cfg.provider}")