from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class StepType(StrEnum):
    OCR = "ocr"


class PlanAction(StrEnum):
    PLAN = "PLAN"
    SKIP = "SKIP"


class RunStatus(StrEnum):
    PENDING = "pending"
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    id: int = Field(ge=1)
    title: str = Field(min_length=1)
    type: StepType
    input: str = Field(min_length=1)
    output: str = Field(min_length=1)
    success_criteria: list[str] = Field(min_length=1)


class PlanResult(BaseModel):
    goal: str = ""
    action: PlanAction = PlanAction.PLAN
    schema_name: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self) -> "PlanResult":
        if self.action == PlanAction.PLAN:
            if not self.goal.strip():
                raise ValueError("goal must not be empty when action is PLAN")
            if not self.schema_name or not self.schema_name.strip():
                raise ValueError("schema_name must not be empty when action is PLAN")
            if not self.steps:
                raise ValueError("steps must not be empty when action is PLAN")
        else:
            if self.steps:
                raise ValueError("steps must be empty when action is SKIP")
        return self


class StepResult(BaseModel):
    step_id: int = Field(ge=1)
    executor: str = Field(min_length=1)
    content: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)


class CriticIssue(BaseModel):
    severity: Literal["low", "medium", "high"]
    description: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class CriticResult(BaseModel):
    approved: bool
    issues: list[CriticIssue] = Field(default_factory=list)
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_issues_on_reject(self) -> "CriticResult":
        if not self.approved and not self.issues:
            raise ValueError("issues must not be empty when approved is False")
        return self


@dataclass
class RunContext:
    user_request: str
    document_content: str
    plan: PlanResult | None = None
    active_schema: str | None = None
    steps_results: list[StepResult] = field(default_factory=list)
    critic_feedback: list[CriticIssue] = field(default_factory=list)
    status: RunStatus = RunStatus.PENDING


class OcrResult(BaseModel):
    document_path: str
    schema_name: str | None
    yaml_content: str
    step_results: list[StepResult]
    retry_count: int
    status: RunStatus



def _to_plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {k: _to_plain(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    return value



def run_context_to_dict(context: RunContext) -> dict[str, Any]:
    return {
        "user_request": context.user_request,
        "document_content": context.document_content,
        "plan": _to_plain(context.plan),
        "active_schema": context.active_schema,
        "steps_results": _to_plain(context.steps_results),
        "critic_feedback": _to_plain(context.critic_feedback),
        "status": context.status.value,
    }



def run_context_to_yaml(context: RunContext) -> str:
    return yaml.safe_dump(
        run_context_to_dict(context),
        allow_unicode=True,
        sort_keys=False,
    )



def run_context_from_dict(data: dict[str, Any]) -> RunContext:
    return RunContext(
        user_request=data.get("user_request", ""),
        document_content=data.get("document_content", ""),
        plan=PlanResult.model_validate(data["plan"]) if data.get("plan") else None,
        active_schema=data.get("active_schema"),
        steps_results=[StepResult.model_validate(item) for item in data.get("steps_results", [])],
        critic_feedback=[CriticIssue.model_validate(item) for item in data.get("critic_feedback", [])],
        status=RunStatus(data.get("status", RunStatus.PENDING.value)),
    )



def run_context_from_yaml(text: str) -> RunContext:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("RunContext YAML must deserialize to a mapping")
    return run_context_from_dict(data)



def load_run_context(path: str | Path) -> RunContext:
    return run_context_from_yaml(Path(path).read_text(encoding="utf-8"))
