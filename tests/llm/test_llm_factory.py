import asyncio

from common.types import AppConfig, ChatRequest, Message
from llm.factory import create_llm_factory
from llm.mock import MockLLMClient
from llm.openai_client import OpenAICompatibleClient


def test_create_llm_factory_returns_openai_client_for_openai_provider():
    app_cfg = AppConfig.model_validate(
        {"version": "1.0", "llm": {"provider": "openai", "base_url": "http://localhost:4000"}, "db": {"path": ".data/db/advisor.sqlite"}}
    )
    factory = create_llm_factory(env="prod", app_cfg=app_cfg)
    llm = factory.for_model("planner-model")
    assert isinstance(llm, OpenAICompatibleClient)


def test_create_llm_factory_returns_mock_client_for_test_env():
    app_cfg = AppConfig.model_validate(
        {"version": "1.0", "llm": {"provider": "openai", "base_url": "http://localhost:4000"}, "db": {"path": ".data/db/advisor.sqlite"}}
    )
    factory = create_llm_factory(env="test", app_cfg=app_cfg)
    llm = factory.for_model("mock-model")
    assert isinstance(llm, MockLLMClient)


def test_bound_clients_return_model_alias_in_response():
    app_cfg = AppConfig.model_validate(
        {"version": "1.0", "llm": {"provider": "mock"}, "db": {"path": ".data/db/advisor.sqlite"}}
    )
    factory = create_llm_factory(env="test", app_cfg=app_cfg)
    llm = factory.for_model("planner-model")

    response = asyncio.run(
        llm.chat(
            ChatRequest(
                messages=[Message(role="user", content="hello")],
            )
        )
    )

    assert response.model_alias == "planner-model"
