from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    """
    Provider-neutral chat message.

    We use a minimal, vendor-agnostic representation (role + text content).
    Provider-specific message formats are handled inside LLM adapters.
    """
    role: Role
    content: str


class ChatRequest(BaseModel):
    """
    Provider-neutral chat request.

    `model` is a model alias (e.g. from LiteLLM config).
    Optional generation parameters are kept here in a generic form.
    """
    model: str
    messages: list[Message]
    temperature: float | None = None
    max_tokens: int | None = None


class ChatResponse(BaseModel):
    """
    Provider-neutral chat response.

    For MVP we only keep the final text content.
    Provider-specific metadata (usage, raw response, etc.) can be added later.
    """
    text: str