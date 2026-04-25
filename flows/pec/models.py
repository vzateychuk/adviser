from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


# =============================================================================
# ENUMS
# =============================================================================


class StepType(StrEnum):
    """Extraction step type."""
    OCR = "ocr"


class PlanAction(StrEnum):
    """Planner decision action."""
    PLAN = "PLAN"
    SKIP = "SKIP"


class RunStatus(StrEnum):
    """Pipeline execution status."""
    PENDING = "pending"
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# =============================================================================
# PLAN MODELS
# =============================================================================


class PlanStep(BaseModel):
    """Single extraction step in the plan.

    Represents one atomic extraction task that the executor will perform.
    """

    id: int = Field(
        ge=1,
        description="Unique step identifier, starting from 1",
    )
    title: str = Field(
        min_length=1,
        description="Human-readable step title",
    )
    type: StepType = Field(
        description="Step type: 'ocr' for document extraction",
    )
    input: str = Field(
        min_length=1,
        description="Input source identifier (e.g., 'document_content')",
    )
    output: str = Field(
        min_length=1,
        description="Target schema name for extraction output",
    )
    success_criteria: list[str] = Field(
        min_length=1,
        description="Criteria the critic will verify against",
    )


class PlanResult(BaseModel):
    """Result of the planning phase.

    Contains the extraction goal, target schema, and steps to execute.
    This is the contract between Planner and Executor.
    """

    goal: str = Field(
        default="",
        description="Brief description of the extraction goal",
    )
    action: PlanAction = Field(
        default=PlanAction.PLAN,
        description="PLAN to process, SKIP to reject document",
    )
    schema_name: str | None = Field(
        default=None,
        description="Target schema ID from catalog (null for SKIP)",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made during planning",
    )
    steps: list[PlanStep] = Field(
        default_factory=list,
        description="Extraction steps (empty for SKIP)",
    )

    @model_validator(mode="after")
    def validate_shape(self) -> "PlanResult":
        """Ensure PLAN has required fields and SKIP has none."""
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


# =============================================================================
# EXECUTION MODELS
# =============================================================================


class StepResult(BaseModel):
    """Result of executing a single step.

    Contains the extracted medical document and any assumptions made by the executor.
    """

    step_id: int = Field(
        ge=1,
        description="ID of the step that produced this result",
    )
    executor: str = Field(
        min_length=1,
        description="Executor type that produced this result (e.g., 'ocr')",
    )
    doc: "MedicalDoc | None" = Field(
        default=None,
        description="Typed medical extraction (None only for skipped/failed steps)",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made during extraction",
    )


# =============================================================================
# CRITIC MODELS (structured output schema)
# =============================================================================


class CriticIssue(BaseModel):
    """Single issue found by the critic.

    Used for both structured LLM output and internal representation.
    """

    severity: Literal["low", "medium", "high"] = Field(
        description="Issue severity: low (minor), medium (should fix), high (must fix)",
    )
    description: str = Field(
        min_length=1,
        description="Clear description of what's wrong",
    )
    suggestion: str = Field(
        min_length=1,
        description="Actionable suggestion for fixing the issue",
    )


class CriticResult(BaseModel):
    """Result of the critic review.

    Indicates whether the extraction is approved and lists any issues found.
    This schema is used directly with instructor for structured outputs.
    """

    approved: bool = Field(
        description="True if extraction meets all criteria, False if issues found",
    )
    issues: list[CriticIssue] = Field(
        default_factory=list,
        description="List of issues found (empty when approved=True)",
    )
    summary: str = Field(
        min_length=1,
        description="Brief summary of the review verdict",
    )

    @model_validator(mode="after")
    def check_issues_on_reject(self) -> "CriticResult":
        """Ensure rejected results have at least one issue."""
        if not self.approved and not self.issues:
            raise ValueError("issues must not be empty when approved is False")
        return self


# =============================================================================
# MEDICAL EXTRACTION MODELS
# =============================================================================


class DocumentInfo(BaseModel):
    """Метаданные документа."""

    date: str | None = Field(
        default=None,
        description="Дата документа в формате как в источнике (например, '2020-02-09')",
    )
    organization: str | None = Field(
        default=None,
        description="Название медицинского учреждения",
    )
    doctor: str | None = Field(
        default=None,
        description="ФИО врача",
    )
    specialty: str | None = Field(
        default=None,
        description="Специальность врача (например, 'УЗИ-диагностика', 'Терапевт')",
    )


class PatientInfo(BaseModel):
    """Информация о пациенте."""

    full_name: str | None = Field(
        default=None,
        description="Полное ФИО пациента",
    )
    birth_date: str | None = Field(
        default=None,
        description="Дата рождения в формате как в источнике",
    )
    gender: Literal["male", "female", "unknown"] | None = Field(
        default=None,
        description="Пол пациента",
    )


class Measurement(BaseModel):
    """Универсальное измерение.

    Используется для:
    - Лабораторных показателей (гемоглобин, глюкоза)
    - Измерений на УЗИ/КТ/МРТ (размеры органов)
    - Физикальных данных (АД, пульс, температура)
    """

    name: str = Field(
        description="Название показателя (например, 'Гемоглобин', 'Толщина стенки')",
    )
    value: str = Field(
        description="Значение как в документе (например, '140', '12', '120/80')",
    )
    unit: str | None = Field(
        default=None,
        description="Единица измерения (например, 'г/л', 'мм', 'мм рт.ст.')",
    )
    reference_range: str | None = Field(
        default=None,
        description="Референсный диапазон (например, '120-160', '< 5.5')",
    )
    status: Literal["normal", "low", "high", "abnormal", "unknown"] = Field(
        default="unknown",
        description="Статус относительно нормы",
    )
    notes: str | None = Field(
        default=None,
        description="Дополнительные комментарии к показателю",
    )


class Medication(BaseModel):
    """Информация о препарате."""

    name: str = Field(
        description="Название препарата",
    )
    dosage: str | None = Field(
        default=None,
        description="Дозировка (например, '500 мг', '10 мл')",
    )
    frequency: str | None = Field(
        default=None,
        description="Частота приёма (например, '2 раза в день', 'утром натощак')",
    )
    duration: str | None = Field(
        default=None,
        description="Длительность курса (например, '14 дней', '1 месяц')",
    )
    route: str | None = Field(
        default=None,
        description="Способ приёма (например, 'перорально', 'в/м', 'наружно')",
    )


class MedicalDoc(BaseModel):
    """Универсальная схема медицинского документа.

    Единая структура для всех типов документов:
    - lab: лабораторные анализы
    - diagnostic: УЗИ, рентген, КТ, МРТ
    - consultation: консультации врачей
    - medication_trace: назначения, рецепты

    LLM заполняет релевантные поля, остальные остаются пустыми.
    """

    # === ИДЕНТИФИКАЦИЯ ===
    schema_id: Literal["lab", "diagnostic", "consultation", "medication_trace"] = Field(
        description="Тип документа, определённый Planner'ом",
    )

    # === ОБЩИЕ СЕКЦИИ ===
    document: DocumentInfo = Field(
        default_factory=DocumentInfo,
        description="Метаданные документа",
    )
    patient: PatientInfo = Field(
        default_factory=PatientInfo,
        description="Информация о пациенте",
    )

    # === ИЗМЕРЕНИЯ (lab, diagnostic) ===
    measurements: list[Measurement] = Field(
        default_factory=list,
        description=(
            "Числовые измерения: "
            "для lab — анализы (гемоглобин, глюкоза); "
            "для diagnostic — размеры органов, объёмы"
        ),
    )

    # === ТЕКСТОВЫЕ НАХОДКИ (diagnostic, consultation) ===
    findings: list[str] = Field(
        default_factory=list,
        description=(
            "Текстовые находки и наблюдения: "
            "описания на УЗИ, результаты осмотра, жалобы"
        ),
    )

    # === ДИАГНОЗЫ (consultation, diagnostic) ===
    diagnoses: list[str] = Field(
        default_factory=list,
        description="Диагнозы (основной и сопутствующие)",
    )

    # === РЕКОМЕНДАЦИИ (все типы) ===
    recommendations: list[str] = Field(
        default_factory=list,
        description="Рекомендации врача, назначения на обследования",
    )

    # === ПРЕПАРАТЫ (medication_trace, consultation) ===
    medications: list[Medication] = Field(
        default_factory=list,
        description="Назначенные или принимаемые препараты",
    )

    # === ЗАКЛЮЧЕНИЕ ===
    conclusion: str | None = Field(
        default=None,
        description="Общее заключение документа",
    )

    # === ДОПОЛНИТЕЛЬНО ===
    procedure_name: str | None = Field(
        default=None,
        description="Название процедуры/исследования (для diagnostic)",
    )
    notes: str | None = Field(
        default=None,
        description="Дополнительные заметки, не вошедшие в другие поля",
    )

    def merge(self, other: "MedicalDoc") -> "MedicalDoc":
        """Incremental merge. self = накопленный doc, other = результат нового шага.
        Возвращает новый объект, self/other не мутируются.
        """
        if self.schema_id != other.schema_id:
            log.warning(
                "Schema ID mismatch in MedicalDoc.merge: self=%s, other=%s, using self",
                self.schema_id, other.schema_id,
            )

        def _merge_scalar_fields(base: "DocumentInfo | PatientInfo | None", new: "DocumentInfo | PatientInfo | None", model_cls: type) -> "DocumentInfo | PatientInfo | None":
            """Per-field merge двух Pydantic-объектов: new wins if non-null, else base."""
            if base is None and new is None:
                return None
            if base is None:
                return new
            if new is None:
                return base
            merged = {}
            for field_name in model_cls.model_fields:
                base_val = getattr(base, field_name)
                new_val = getattr(new, field_name)
                merged[field_name] = new_val if new_val is not None else base_val
            return model_cls(**merged)

        def _dedup_strings(items: list[str]) -> list[str]:
            """Сохранить порядок, убрать дубликаты по string-equality."""
            seen: set[str] = set()
            out: list[str] = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

        def _dedup_by_name(items: list["Measurement | Medication"], key_fn) -> list["Measurement | Medication"]:
            """Дедуп по case-insensitive name, 'later wins' при конфликте."""
            index: dict[str, int] = {}
            out: list["Measurement | Medication"] = []
            for item in items:
                name_key = key_fn(item).strip().lower()
                if name_key in index:
                    out[index[name_key]] = item
                else:
                    index[name_key] = len(out)
                    out.append(item)
            return out

        # notes: конкатенация через \n\n если оба non-null
        if self.notes and other.notes:
            merged_notes = f"{self.notes}\n\n{other.notes}"
        else:
            merged_notes = other.notes if other.notes is not None else self.notes

        return MedicalDoc(
            schema_id=self.schema_id,
            document=_merge_scalar_fields(self.document, other.document, DocumentInfo),
            patient=_merge_scalar_fields(self.patient, other.patient, PatientInfo),
            procedure_name=other.procedure_name if other.procedure_name is not None else self.procedure_name,
            conclusion=other.conclusion if other.conclusion is not None else self.conclusion,
            notes=merged_notes,
            findings=_dedup_strings(self.findings + other.findings),
            diagnoses=_dedup_strings(self.diagnoses + other.diagnoses),
            recommendations=_dedup_strings(self.recommendations + other.recommendations),
            measurements=_dedup_by_name(self.measurements + other.measurements, lambda m: m.name),
            medications=_dedup_by_name(self.medications + other.medications, lambda m: m.name),
        )


# =============================================================================
# RUN CONTEXT (shared state across pipeline)
# =============================================================================


@dataclass
class RunContext:
    """Shared state passed through the PEC pipeline.

    RunContext is the single source of truth for:
    - Input: user_request and document_content
    - Planning: plan and active_schema
    - Execution: steps_results
    - Review: critic_feedback and status

    Each stage reads what it needs and writes its output to the context.
    The Orchestrator manages transitions between stages.

    Design notes:
    - Dataclass (not Pydantic) because this is internal state, not LLM I/O
    - Mutable: stages update fields in place
    - Serializable: can be dumped to YAML for debugging and CLI handoff
    """

    # Input (immutable after creation)
    user_request: str
    """Original user request or document path."""

    document_content: str
    """Full text content of the document to process."""

    # Planning output
    plan: PlanResult | None = None
    """Planner output: goal, schema, and extraction steps."""

    active_schema: str | None = None
    """Currently active schema ID (derived from plan)."""

    # Execution output
    steps_results: list[StepResult] = field(default_factory=list)
    """Results from executed steps, in order."""

    doc: "MedicalDoc | None" = None
    """Incremental merged medical extraction (accumulated after each step)."""

    # Review state
    critic_feedback: list[CriticIssue] = field(default_factory=list)
    """Current critic feedback (cleared between retries)."""

    status: RunStatus = RunStatus.PENDING
    """Current pipeline status."""


# =============================================================================
# FINAL OUTPUT
# =============================================================================


class OcrResult(BaseModel):
    """Final result of the OCR pipeline.

    This is the top-level output returned to callers after the full
    PEC pipeline completes (or fails/skips).
    """

    document_path: str = Field(
        description="Path or identifier of the processed document",
    )
    schema_name: str | None = Field(
        description="Schema used for extraction (null if skipped)",
    )
    context: str = Field(
        description="Extracted data as JSON (empty if skipped/failed)",
    )
    step_results: list[StepResult] = Field(
        description="Results from each extraction step",
    )
    retry_count: int = Field(
        ge=0,
        description="Total retries across all steps",
    )
    status: RunStatus = Field(
        description="Final pipeline status",
    )


# =============================================================================
# SERIALIZATION HELPERS
# =============================================================================


def _to_plain(value: Any) -> Any:
    """Convert nested Pydantic/dataclass/enum to plain dict/list."""
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
    """Convert RunContext to a plain dict for serialization."""
    return {
        "user_request": context.user_request,
        "document_content": context.document_content,
        "plan": _to_plain(context.plan),
        "active_schema": context.active_schema,
        "steps_results": _to_plain(context.steps_results),
        "doc": _to_plain(context.doc),
        "critic_feedback": _to_plain(context.critic_feedback),
        "status": context.status.value,
    }


def run_context_to_yaml(context: RunContext) -> str:
    """Serialize RunContext to YAML for CLI output and debugging."""
    return yaml.safe_dump(
        run_context_to_dict(context),
        allow_unicode=True,
        sort_keys=False,
    )


def run_context_from_dict(data: dict[str, Any]) -> RunContext:
    """Reconstruct RunContext from a plain dict."""
    return RunContext(
        user_request=data.get("user_request", ""),
        document_content=data.get("document_content", ""),
        plan=PlanResult.model_validate(data["plan"]) if data.get("plan") else None,
        active_schema=data.get("active_schema"),
        steps_results=[StepResult.model_validate(item) for item in data.get("steps_results", [])],
        doc=MedicalDoc.model_validate(data["doc"]) if data.get("doc") else None,
        critic_feedback=[CriticIssue.model_validate(item) for item in data.get("critic_feedback", [])],
        status=RunStatus(data.get("status", RunStatus.PENDING.value)),
    )


def run_context_from_yaml(text: str) -> RunContext:
    """Parse RunContext from YAML string."""
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("RunContext YAML must deserialize to a mapping")
    return run_context_from_dict(data)


def load_run_context(path: str | Path) -> RunContext:
    """Load RunContext from a YAML file."""
    return run_context_from_yaml(Path(path).read_text(encoding="utf-8"))
