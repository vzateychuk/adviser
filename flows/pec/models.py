from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator
from typing import Literal


class StepType(StrEnum):
    OCR = "ocr"


class PlanStep(BaseModel):
    """
    One executable step produced by the Planner.

    For the OCR PEC flow each step represents a single extraction unit:
    - document path via `input`
    - expected YAML schema name via `output`
    - verifiable criteria via `success_criteria`
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

    Produced by Planner from document context (file path + doc type).
    Consumed by PecOrchestrator to execute OCR steps sequentially.
    """

    goal: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(min_length=1)


class StepResult(BaseModel):
    """
    OcrExecutor output artifact for a single step.

    `content` holds YAML-structured data extracted by the OCR model.
    `executor` is always "ocr" in this flow.
    """

    step_id: int = Field(ge=1)
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
    def check_issues_on_reject(self) -> "CriticResult":
        if not self.approved and not self.issues:
            raise ValueError("issues must not be empty when approved is False")
        return self


class OcrResult(BaseModel):
    """
    Final output of the OCR PEC flow.

    Returned to Coordinator after all steps pass Critic approval.
    Coordinator is responsible for persisting this data to GitHub/storage.
    """

    document_path: str
    schema_name: str
    yaml_content: str
    step_results: list[StepResult]
    retry_count: int
