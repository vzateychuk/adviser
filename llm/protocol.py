from __future__ import annotations

from typing import Protocol

from llm.types import ChatRequest, ChatResponse


class LLMClient(Protocol):
    async def chat(self, req: ChatRequest) -> ChatResponse: ...