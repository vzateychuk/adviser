from __future__ import annotations

from typing import Callable

from llm.types import ChatRequest, ChatResponse


MockScenario = Callable[[ChatRequest], ChatResponse]



def _last_user(req: ChatRequest) -> str:
    return next((m.content for m in reversed(req.messages) if m.role == "user"), "")



def planner_mock(req: ChatRequest) -> ChatResponse:
    user = _last_user(req).lower()
    if "not medical" in user or "shopping list" in user:
        return ChatResponse(
            text=(
                "action: SKIP\n"
                "goal: Input is not a medical document\n"
                "schema_name: null\n"
                "assumptions: []\n"
                "steps: []\n"
            )
        )
    text = _last_user(req)
    schema_name = "lab" if any(token in user for token in ["lab", "??????", "blood", "hemoglobin"]) else "consultation"
    return ChatResponse(
        text=(
            "action: PLAN\n"
            "goal: Extract medical data from document\n"
            f"schema_name: {schema_name}\n"
            "assumptions:\n"
            "  - deterministic test scenario\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Extract document data\n"
            "    type: ocr\n"
            f"    input: {schema_name}_document\n"
            f"    output: {schema_name}\n"
            "    success_criteria:\n"
            "      - all numeric values match the source\n"
            "      - all dates match the source\n"
            "      - all units match the source when present\n"
        )
    )



def ocr_executor_mock(req: ChatRequest) -> ChatResponse:
    user = _last_user(req).lower()
    if "active_schema: lab" in user:
        return ChatResponse(
            text=(
                "document:\n"
                "  date: '2024-01-01'\n"
                "  org: Mock Lab\n"
                "  source_ref: mock_document\n"
                "patient:\n"
                "  full_name: Mock Patient\n"
                "  surname: Patient\n"
                "  birth_date: null\n"
                "laboratory_panel:\n"
                "  results:\n"
                "    - analyte: Hemoglobin\n"
                "      value: '120'\n"
                "      unit: g/L\n"
                "      reference_range: 120-160\n"
            )
        )
    return ChatResponse(
        text=(
            "document:\n"
            "  date: '2024-01-01'\n"
            "patient:\n"
            "  full_name: Mock Patient\n"
            "consultation:\n"
            "  summary: Follow-up visit\n"
        )
    )



def critic_mock(req: ChatRequest) -> ChatResponse:
    return ChatResponse(text="approved: true\nsummary: Mock critic approval\nissues: []\n")



def default_mock(req: ChatRequest) -> ChatResponse:
    return ChatResponse(text=f"[MOCK] {_last_user(req)}")
