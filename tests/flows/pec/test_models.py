import pytest
from pydantic import ValidationError

from flows.pec.models import CriticResult, OcrResult, PlanResult, PlanStep, StepResult


def test_plan_validates_and_serializes():
    """
    PlanResult round-trip: construct -> model_dump -> model_validate.
    Simulates JSON persistence (SQLite read-back).
    """
    plan = PlanResult(
        goal="Extract blood test data",
        schema_name="blood_test",
        assumptions=["A1"],
        steps=[
            PlanStep(
                id=1,
                title="Extract values",
                type="ocr",
                input="scan.pdf",
                output="blood_test",
                success_criteria=["all numeric values match"],
            )
        ],
    )

    data = plan.model_dump()
    plan2 = PlanResult.model_validate(data)

    assert plan2.goal == "Extract blood test data"
    assert plan2.schema_name == "blood_test"
    assert plan2.steps[0].id == 1
    assert plan2.steps[0].type == "ocr"


def test_plan_rejects_empty_steps():
    """PlanResult with no steps must be rejected (orchestrator cannot execute)."""
    with pytest.raises(ValidationError):
        PlanResult(goal="x", schema_name="s", steps=[])


def test_critic_requires_summary():
    """CriticResult.summary must be non-empty (used in logs and retry decisions)."""
    with pytest.raises(ValidationError):
        CriticResult(approved=True, issues=[], summary="")


def test_critic_requires_issues_on_reject():
    """CriticResult with approved=False must have at least one issue."""
    with pytest.raises(ValidationError):
        CriticResult(approved=False, issues=[], summary="rejected")


def test_ocr_result_fields():
    """OcrResult stores document path, schema, YAML content and metadata."""
    step_result = StepResult(step_id=1, executor="ocr", content="key: value")
    result = OcrResult(
        document_path="scan.pdf",
        schema_name="blood_test",
        yaml_content="key: value",
        step_results=[step_result],
        retry_count=0,
    )
    assert result.document_path == "scan.pdf"
    assert result.retry_count == 0