import pytest
from pydantic import ValidationError

from flows.pec.models import (
    CriticIssue,
    CriticResult,
    OcrResult,
    PlanAction,
    PlanResult,
    PlanStep,
    RunContext,
    RunStatus,
    StepResult,
    run_context_from_yaml,
    run_context_to_yaml,
)



def test_plan_validates_and_serializes():
    plan = PlanResult(
        goal="Extract blood test data",
        action=PlanAction.PLAN,
        schema_name="lab",
        assumptions=["A1"],
        steps=[
            PlanStep(
                id=1,
                title="Extract values",
                type="ocr",
                input="scan.pdf",
                output="lab",
                success_criteria=["all numeric values match"],
            )
        ],
    )

    data = plan.model_dump()
    plan2 = PlanResult.model_validate(data)

    assert plan2.goal == "Extract blood test data"
    assert plan2.schema_name == "lab"
    assert plan2.steps[0].id == 1
    assert plan2.steps[0].type == "ocr"



def test_plan_rejects_empty_steps_for_plan_action():
    with pytest.raises(ValidationError):
        PlanResult(goal="x", action=PlanAction.PLAN, schema_name="lab", steps=[])



def test_skip_plan_allows_empty_steps_and_null_schema():
    plan = PlanResult(goal="not medical", action=PlanAction.SKIP, schema_name=None, steps=[])
    assert plan.action == PlanAction.SKIP



def test_critic_requires_summary():
    with pytest.raises(ValidationError):
        CriticResult(approved=True, issues=[], summary="")



def test_critic_requires_issues_on_reject():
    with pytest.raises(ValidationError):
        CriticResult(approved=False, issues=[], summary="rejected")



def test_ocr_result_fields():
    step_result = StepResult(step_id=1, executor="ocr", content="key: value")
    result = OcrResult(
        document_path="scan.pdf",
        schema_name="lab",
        yaml_content="key: value",
        step_results=[step_result],
        retry_count=0,
        status=RunStatus.COMPLETED,
    )
    assert result.document_path == "scan.pdf"
    assert result.retry_count == 0



def test_run_context_yaml_roundtrip_preserves_strings():
    context = RunContext(
        user_request="scan.pdf",
        document_content="Hb 120 g/L 2024-01-01",
        plan=PlanResult(
            goal="Extract lab data",
            action=PlanAction.PLAN,
            schema_name="lab",
            steps=[
                PlanStep(
                    id=1,
                    title="Extract lab values",
                    type="ocr",
                    input="scan.pdf",
                    output="lab",
                    success_criteria=["every unit matches source"],
                )
            ],
        ),
        active_schema="lab",
        steps_results=[StepResult(step_id=1, executor="ocr", content="value: '120'\nunit: g/L\ndate: '2024-01-01'")],
        critic_feedback=[CriticIssue(severity="high", description="Missing range", suggestion="Add reference range")],
        status=RunStatus.EXECUTING,
    )

    yaml_text = run_context_to_yaml(context)
    restored = run_context_from_yaml(yaml_text)

    assert restored.active_schema == "lab"
    assert "'120'" in restored.steps_results[0].content
    assert "'2024-01-01'" in restored.steps_results[0].content
    assert restored.critic_feedback[0].description == "Missing range"
