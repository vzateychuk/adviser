import pytest
from pydantic import ValidationError

from flows.pec.models import PlanResult, PlanStep, CriticResult


def test_plan_validates_and_serializes():
    """
    This test ensures that:
    1) A valid PlanResult object can be constructed (Pydantic validation passes).
    2) The model can be serialized to a plain dict (model_dump).
    3) The same dict can be validated back into a PlanResult (model_validate),
       which simulates JSON round-trip persistence (e.g., storing in SQLite and reading back).
    """
    plan = PlanResult(
        goal="Do something",
        assumptions=["A1"],
        steps=[
            PlanStep(
                id=1,
                title="Step 1",
                type="generic",
                input="in",
                output="out",
                success_criteria=["c1"],
            )
        ],
    )

    data = plan.model_dump()
    plan2 = PlanResult.model_validate(data)

    assert plan2.goal == "Do something"
    assert plan2.steps[0].id == 1


def test_plan_rejects_empty_steps():
    """
    The orchestrator cannot execute an empty plan.
    This test checks that Pydantic validation rejects PlanResult with no steps.
    """
    with pytest.raises(ValidationError):
        PlanResult(goal="x", steps=[])


def test_critic_requires_summary():
    """
    CriticResult.summary is required to be non-empty.
    This ensures the critic always provides a short verdict explanation
    suitable for logging and for retry decisions.
    """
    with pytest.raises(ValidationError):
        CriticResult(approved=True, issues=[], summary="")