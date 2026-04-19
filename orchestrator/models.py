from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator
from typing import Literal

from dataclasses import dataclass, field


class StepType(StrEnum):
    GENERIC = "generic"
    CODE = "code"

class PlanStep(BaseModel):
    """
    One executable step produced by the Planner.

    This is the main unit of work for the planner–executor architecture.
    Each step is designed to be executed independently by an executor (generic or code)
    and should include enough information to:
    - route to the right executor (via `type`)
    - define expected output (`output`)
    - allow objective verification (`success_criteria`)
    """

    id: int = Field(ge=1)
    title: str = Field(min_length=1)
    type: StepType
    input: str = Field(min_length=1)
    output: str = Field(min_length=1)
    success_criteria: list[str] = Field(min_length=1)


class PlanResult(BaseModel):
    """
    Planner output artifact.

    Represents a structured plan to solve the user task step-by-step.
    This object is intended to be:
    - produced by Planner (from JSON)
    - validated by Pydantic (to prevent malformed plans)
    - persisted as JSON in SQLite (later)
    - consumed by the orchestrator to execute steps sequentially
    """

    goal: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(min_length=1)


class StepResult(BaseModel):
    """
    Executor output artifact for a single step.

    Stores the result of executing one PlanStep. In MVP it is a single `content` string,
    which can be either:
    - a natural language result (generic executor)
    - code output (code executor)

    `executor` is a plain str (not a Literal) so new executor types can be added
    without modifying this artifact model.

    Later this can be extended with more structure (e.g., files, patches, tool calls, etc.).
    """

    id: int = Field(ge=1)
    executor: str = Field(min_length=1)
    content: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)


class CriticIssue(BaseModel):
    """
    One concrete issue found by the Critic.

    The Critic should provide actionable feedback. Each issue must include:
    - severity level (used by retry policy / prioritization)
    - description of what is wrong
    - suggestion with a concrete fix action
    """

    severity: Literal["low", "medium", "high"]
    description: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class CriticResult(BaseModel):
    """
    Critic verdict artifact.

    Used by the critic loop to decide whether to accept the step result or retry it.
    This model is aligned with the critic prompt: JSON-only output with:
    - approved: boolean verdict
    - issues: empty if approved==True; non-empty if approved==False
    - summary: short one-sentence verdict
    """

    approved: bool
    issues: list[CriticIssue] = Field(default_factory=list)
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_issues_on_reject(self) -> CriticResult:
        if not self.approved and not self.issues:
            raise ValueError("issues must not be empty when approved is False")
        return self

# Создание enum для status
class RunStatus(StrEnum):
  SUCCESS = "SUCCESS"
  FAIL = "FAIL"


@dataclass
class RunContext:
  user_request: str
  plan: PlanResult | None = None
  step_results: list[StepResult] = field(default_factory=list)
  critic_feedback: CriticResult | None = None
  max_retries: int = 3
  status: RunStatus | None = None