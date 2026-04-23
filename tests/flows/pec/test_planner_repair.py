from __future__ import annotations

import pytest

from flows.pec.planner import Planner
from flows.pec.schema_catalog import SchemaCatalog
from llm.types import ChatResponse


class _FakeLLM:
    def __init__(self, text: str):
        self._text = text

    async def chat(self, req):  # noqa: ANN001
        return ChatResponse(text=self._text)


@pytest.mark.asyncio
async def test_planner_repairs_close_schema_alias_and_step_fields():
    planner = Planner(
        llm=_FakeLLM(
            """
action: PLAN
goal: Extract lab panel data
schema_name: lab_panel
steps:
  - id: 1
    title: Extract Lab Panel Data
    type: OCR
    input: document_content
    output: lab_panel
    success_criteria: []
"""
        ),
        system_prompt="system",
        user_template="user",
        schema_catalog=SchemaCatalog("flows/pec/schemas"),
    )

    plan = await planner.plan(user_request="doc", document_content="Hb 120 g/L")

    assert plan.schema_name == "lab"
    assert plan.steps[0].output == "lab"
    assert plan.steps[0].type == "ocr"
    assert plan.steps[0].success_criteria
