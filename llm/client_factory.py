from __future__ import annotations

from typing import Protocol

from llm.protocol import LLMClient


class LLMClientFactory(Protocol):
    def for_model(self, model_alias: str) -> LLMClient: ...
