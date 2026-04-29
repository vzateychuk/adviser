from __future__ import annotations
import pytest
from flows.pec.planner import Planner
from flows.pec.schema_catalog import SchemaCatalog
from common.types import ChatResponse


class _FakeLLM:
    def __init__(self, text: str):
        self._text = text

    async def chat(self, req):  # noqa: ANN001
        return ChatResponse(text=self._text)

    async def chat_structured(self, req, response_model, **kwargs):  # noqa: ANN001
        # Simulate structured output as real LLM would, returning PlanResult
        from flows.pec.models import PlanResult, PlanStep, StepType
        return PlanResult(
            goal="Extract lab panel data",
            action="PLAN",  # planner accepts PLAN and normalizes to PLAN
            schema_name="lab",  # planner normalizes from lab_panel to lab
            steps=[
                PlanStep(
                    id=1,
                    title="Extract Lab Panel Data",
                    type=StepType.OCR,  # Exact enum, not 'OCR' string
                    input="document_content",
                    output="lab",
                    success_criteria=["dummy criteria"],  # Minimum 1 item
                )
            ],
        )


@pytest.mark.asyncio
async def test_planner_repairs_close_schema_alias_and_step_fields():
    from flows.pec.models import StepResult

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
              success_criteria:
              - dummy
            """
        ),
        system_prompt="system",
        user_template="user",
        schema_catalog=SchemaCatalog("flows/pec/schemas"),
    )
    plan = await planner.plan(user_request="doc", document_content="Hb 120 g/L")
    # After planner repair and normalization
    assert plan.schema_name == "lab"
    assert plan.steps[0].output == "lab"
    assert plan.steps[0].type.value == "ocr"  # StepType"