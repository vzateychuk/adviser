from __future__ import annotations

from typing import Any, cast
from openai import AsyncOpenAI, APIStatusError

from llm.errors import LLMError
from llm.protocol import LLMClient
from llm.types import ChatRequest, ChatResponse


class OpenAICompatibleClient(LLMClient):
    """
    Adapter for OpenAI-compatible Chat Completions API.

    This client is intended to be used with OpenAI-compatible endpoint (e.g. /v1/chat/completions).

    Notes:
    - We keep the rest of the application vendor-agnostic via the LLMClient protocol.
    - openai SDK typing is stricter than our internal message dicts, so we use `cast`
      at the adapter boundary to satisfy static type checkers (Pylance/mypy).
    - Vendor-specific exceptions (APIStatusError) are converted to LLMError here
      so callers outside llm/ never import openai directly.
    """

    def __init__(self, base_url: str) -> None:
        # openai SDK requires an api_key value, even if the proxy handles auth.
        self._client = AsyncOpenAI(base_url=base_url, api_key="dummy")

    async def chat(self, req: ChatRequest) -> ChatResponse:
        messages = cast(list[dict[str, Any]], [m.model_dump() for m in req.messages])

        try:
            resp = await self._client.chat.completions.create(
                model=req.model,
                messages=messages,
                stream=False,
            )
        except APIStatusError as e:
            raise LLMError(str(e), status_code=e.status_code) from e

        text = (resp.choices[0].message.content or "").strip()
        return ChatResponse(text=text)