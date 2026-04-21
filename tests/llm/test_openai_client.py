from __future__ import annotations

import asyncio
from types import SimpleNamespace

import llm.openai_client as openai_client_module

from llm.openai_client import OpenAICompatibleClient
from llm.types import ChatRequest, Message


def test_openai_client_uses_bound_model_alias(monkeypatch):
    captured_kwargs: dict[str, object] = {}

    class DummyCompletions:
        async def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="  hello world  ")
                    )
                ]
            )

    class DummyAsyncOpenAI:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            self.base_url = base_url
            self.api_key = api_key
            self.chat = SimpleNamespace(completions=DummyCompletions())

    monkeypatch.setattr(openai_client_module, "AsyncOpenAI", DummyAsyncOpenAI)

    client = OpenAICompatibleClient(
        base_url="http://localhost:4000",
        model_alias="planner-model",
    )

    response = asyncio.run(
        client.chat(
            ChatRequest(
                messages=[Message(role="user", content="hello")],
            )
        )
    )

    assert captured_kwargs["model"] == "planner-model"
    assert response.text == "hello world"
    assert response.model_alias == "planner-model"
