from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None

    # Optional internal metadata (not sent to providers). Useful for mocks/tests/routing.
    meta: dict[str, str] | None = None


class ChatResponse(BaseModel):
    text: str