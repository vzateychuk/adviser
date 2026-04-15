from __future__ import annotations

from llm.types import ChatRequest, ChatResponse


class MockLLMClient:
    """
    Deterministic fake LLM client for tests.

    Used in env=test to avoid network calls and make tests predictable.
    It returns a simple response based on the last user message.
    """

    async def chat(self, req: ChatRequest) -> ChatResponse:
        last_user_input = ""
        for m in reversed(req.messages):
            if m.role == "user":
                last_user_input = m.content
                break
        return ChatResponse(text=f"[MOCK] {last_user_input}")