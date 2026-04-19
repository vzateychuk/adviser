from __future__ import annotations

import json
from typing import Callable

from llm.types import ChatRequest, ChatResponse


MockScenario = Callable[[ChatRequest], ChatResponse]


# -------------------------
# Planner mock
# -------------------------
def planner_mock(req: ChatRequest) -> ChatResponse:
  payload = {
    "goal": "Mock plan",
    "assumptions": [
      "deterministic test scenario"
    ],
    "steps": [
      {
        "id": 1,
        "title": "Mock step 1",
        "type": "generic",
        "input": "mock input",
        "output": "mock output",
        "success_criteria": [
          "mock criterion"
        ],
      }
    ],
  }

  return ChatResponse(text=json.dumps(payload))

# Executor mock
def executor_mock(req: ChatRequest) -> ChatResponse:
  return ChatResponse(text="Mock executor output: task completed successfully.")

# Critic mock
def critic_mock(req: ChatRequest) -> ChatResponse:
  payload = {
    "approved": True,
    "issues": [],
    "summary": "Mock critic approval",
  }

  return ChatResponse(text=json.dumps(payload))


# -------------------------
# Default mock (optional)
# -------------------------
def default_mock(req: ChatRequest) -> ChatResponse:
  last_user = next(
    (m.content for m in reversed(req.messages) if m.role == "user"),
    "",
  )

  return ChatResponse(text=f"[MOCK] {last_user}")