from __future__ import annotations

from cfg.schema import AppConfig
from llm.mock import MockLLMClient
from llm.openai_client import OpenAICompatibleClient
from llm.protocol import LLMClient


def create_llm(*, env: str, app_cfg: AppConfig) -> LLMClient:
    """
    Creates an LLM client based on app.yaml provider selection.

    Note: env=test can still force mock, but provider is the primary switch.
    """
    if env == "test" or app_cfg.llm.provider == "mock":
        return MockLLMClient()

    if app_cfg.llm.provider == "openai":
        if not app_cfg.llm.base_url:
            raise ValueError("app.yaml: llm.base_url is required for provider=openai")
        return OpenAICompatibleClient(base_url=app_cfg.llm.base_url)

    raise ValueError(f"Unsupported llm.provider: {app_cfg.llm.provider}")