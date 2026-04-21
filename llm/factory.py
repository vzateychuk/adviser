from __future__ import annotations

from cfg.schema import AppConfig
from llm.client_factory import LLMClientFactory
from llm.mock import MockLLMClient
from llm.openai_client import OpenAICompatibleClient
from llm.protocol import LLMClient
from llm.mock_scenarios import (
    critic_mock,
    default_mock,
    ocr_executor_mock,
    planner_mock,
)


class _ConfiguredLLMClientFactory:
    def __init__(self, *, env: str, app_cfg: AppConfig) -> None:
        self._env = env
        self._app_cfg = app_cfg

    def for_model(self, model_alias: str) -> LLMClient:
        cfg = self._app_cfg.llm

        if self._env == "test" or cfg.provider == "mock":
            return MockLLMClient(
                model_alias=model_alias,
                planner=planner_mock,
                ocr_executor=ocr_executor_mock,
                critic=critic_mock,
                default=default_mock,
            )

        if cfg.provider == "openai":
            if not cfg.base_url:
                raise ValueError("app.yaml: llm.base_url is required for provider=openai")
            return OpenAICompatibleClient(base_url=cfg.base_url, model_alias=model_alias)

        raise ValueError(f"Unsupported llm.provider: {cfg.provider}")


def create_llm_factory(*, env: str, app_cfg: AppConfig) -> LLMClientFactory:
    """
    LLM client factory.

    test / mock  -> MockLLMClient with role-based routing (no network)
    openai       -> OpenAICompatibleClient (LiteLLM proxy or OpenAI)
    """
    return _ConfiguredLLMClientFactory(env=env, app_cfg=app_cfg)
