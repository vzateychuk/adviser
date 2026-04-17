from __future__ import annotations

from pydantic import BaseModel
from typing import Literal, Callable


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
  role: Role
  content: str


class LLMConfig(BaseModel):
  provider: str
  base_url: str | None = None

  # TEST ONLY
  mock_mode: Literal["planner", "critic", "default"] | None = None


class TransportMeta(BaseModel):
  request_id: str | None = None
  trace_id: str | None = None
  debug: dict[str, str] | None = None


class ChatRequest(BaseModel):
  model: str
  messages: list[Message]
  temperature: float | None = None
  max_tokens: int | None = None

  # transport/debug only (must not influence orchestration logic)
  meta: TransportMeta | None = None


class ChatResponse(BaseModel):
  text: str


MockScenario = Callable[[ChatRequest], ChatResponse]