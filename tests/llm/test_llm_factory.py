from cfg.schema import AppConfig
from llm.factory import create_llm
from llm.mock import MockLLMClient
from llm.openai_client import OpenAICompatibleClient


def test_create_llm_returns_openai_client_for_openai_provider():
    app_cfg = AppConfig.model_validate(
        {"version": "1.0", "llm": {"provider": "openai", "base_url": "http://localhost:4000"}, "db": {"path": ".data/db/advisor.sqlite"}}
    )
    llm = create_llm(env="prod", app_cfg=app_cfg)
    assert isinstance(llm, OpenAICompatibleClient)