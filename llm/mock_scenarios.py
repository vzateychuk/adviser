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
        "goal": "Extract medical data from document",
        "schema_name": "mock_schema",
        "assumptions": ["deterministic test scenario"],
        "steps": [
            {
                "id": 1,
                "title": "Extract document data",
                "type": "ocr",
                "input": "mock_document.pdf",
                "output": "mock_schema",
                "success_criteria": ["mock criterion"],
            }
        ],
    }
    return ChatResponse(text=json.dumps(payload))


def ocr_executor_mock(req: ChatRequest) -> ChatResponse:
    return ChatResponse(text="patient_name: Mock Patient\ndate: 2024-01-01\nresult: mock_value")


# -------------------------
# Critic mock
# -------------------------
def critic_mock(req: ChatRequest) -> ChatResponse:
    payload = {
        "approved": True,
        "issues": [],
        "summary": "Mock critic approval",
    }
    return ChatResponse(text=json.dumps(payload))


def default_mock(req: ChatRequest) -> ChatResponse:
    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        "",
    )
    return ChatResponse(text=f"[MOCK] {last_user}")