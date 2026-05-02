from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
import logging

import yaml
from pydantic import BaseModel, Field, model_validator, field_validator


log = logging.getLogger(__name__)


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

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: Any) -> str:
        """Normalize action to uppercase PLAN/SKIP. Default to PLAN if unknown."""
        if v is None:
            return PlanAction.PLAN.value
        if isinstance(v, str):
            normalized = v.strip().upper()
            if normalized == "SKIP":
                return PlanAction.SKIP.value
            return PlanAction.PLAN.value
        return PlanAction.PLAN.value


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

    Contains the extracted medical document produced by the executor.
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
        description="Clear description of what is wrong",
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
    summary: str = Field(
        default="",
        description="Brief summary of the review",
    )
    issues: list[CriticIssue] = Field(
        default_factory=list,
        description="List of issues found (empty if approved)",
    )

    @model_validator(mode="after")
    def validate_requirements(self) -> "CriticResult":
        """Validate that required fields are present based on approved status."""
        if self.approved and not self.summary.strip():
            raise ValueError("summary is required when approved")
        if not self.approved and not self.issues:
            raise ValueError("issues are required when not approved")
        return self
    summary: str = Field(
        default="",
        description="Brief summary of the review",
    )
    issues: list[CriticIssue] = Field(
        default_factory=list,
        description="List of issues found (empty if approved)",
    )


# =============================================================================
# MEDICAL DOCUMENT MODELS
# =============================================================================


def _normalize_to_list(v: Any) -> list[str]:
    """Convert value to list[str], handling str/list/None."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


class OrganizationInfo(BaseModel):
    """Medical institution information."""

    name: str | None = Field(
        default=None,
        description="Medical institution name",
    )
    location: str | None = Field(
        default=None,
        description="Address or location",
    )
    department: str | None = Field(
        default=None,
        description="Department or unit",
    )


class DoctorInfo(BaseModel):
    """Doctor information."""

    name: str | None = Field(
        default=None,
        description="Doctor full name",
    )
    specialty: str | None = Field(
        default=None,
        description="Doctor specialty (e.g., 'Ultrasound diagnostic', 'Therapist')",
    )


class DocumentInfo(BaseModel):
    """Document metadata."""

    date: str | None = Field(
        default=None,
        description="Document date as written in source (e.g., '2020-02-09')",
    )
    organization: OrganizationInfo | None = Field(
        default=None,
        description="Medical institution information",
    )
    doctor: DoctorInfo | None = Field(
        default=None,
        description="Doctor information",
    )


class PatientInfo(BaseModel):
    """Patient information."""

    full_name: str | None = Field(
        default=None,
        description="Patient full name",
    )
    birth_date: str | None = Field(
        default=None,
        description="Birth date as written in source",
    )
    gender: Literal["male", "female", "unknown"] | None = Field(
        default=None,
        description="Patient gender",
    )

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v: Any) -> str | None:
        """Normalize Russian gender values to English."""
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        normalized = v.lower().strip()
        # TODO: Load from config/gender_map.yaml at startup
        GENDER_MAP = {
            "мужской": "male", "муж": "male", "м": "male", "male": "male", "m": "male",
            "женский": "female", "жен": "female", "ж": "female", "female": "female", "f": "female",
            "неизвестно": "unknown", "unknown": "unknown", "н": "unknown", "-": "unknown", "": "unknown",
        }
        return GENDER_MAP.get(normalized, v)


class Measurement(BaseModel):
    """Universal measurement.

    Used for:
    - Lab values (hemoglobin, glucose)
    - Ultrasound/CT/MRI measurements (organ sizes)
    - Physical data (blood pressure, pulse, temperature)
    """

    @model_validator(mode="before")
    @classmethod
    def remap_type_to_name(cls, data: Any) -> Any:
        """Remap 'type' field to 'name' if name is missing (LLM sometimes returns type)."""
        if isinstance(data, dict) and "name" not in data and "type" in data:
            data = dict(data)
            data["name"] = data.pop("type")
        return data

    name: str = Field(
        description="Measurement name (e.g., 'Hemoglobin', 'Wall thickness')",
    )
    value: str = Field(
        description="Value as in document (e.g., '140', '12', '120/80')",
    )
    unit: str | None = Field(
        default=None,
        description="Measurement unit (e.g., 'g/L', 'mm', 'mm Hg')",
    )
    reference_range: str | None = Field(
        default=None,
        description="Reference range (e.g., '120-160', '< 5.5')",
    )
    status: Literal["normal", "low", "high", "abnormal", "unknown"] = Field(
        default="unknown",
        description="Status relative to normal range",
    )
    notes: str | None = Field(
        default=None,
        description="Additional comments about the measurement",
    )

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str:
        """Normalize Russian status values to English."""
        if v is None:
            return "unknown"
        if not isinstance(v, str):
            return str(v)
        normalized = v.lower().strip()
        # TODO: Load from config/status_map.yaml at startup
        STATUS_MAP = {
            "норма": "normal", "н": "normal", "normal": "normal",
            "повышен": "high", "высокий": "high", "пов": "high", "повышено": "high", "high": "high",
            "понижен": "low", "низкий": "low", "понижено": "low", "low": "low",
            "отклонение": "abnormal", "abnormal": "abnormal", "откл": "abnormal",
        }
        return STATUS_MAP.get(normalized, "unknown")

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, v: Any) -> str | None:
        """Normalize Russian unit values to English."""
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        normalized = v.lower().strip()
        # TODO: Load from config/unit_map.yaml at startup
        UNIT_MAP = {
            "мсек": "ms", "мс": "ms", "миллисекунда": "ms", "миллисекунды": "ms",
            "сек": "s", "секунда": "s", "секунды": "s",
            "мин": "min", "минута": "min", "минуты": "min",
            "час": "h", "часа": "h", "часов": "h",
            "мг": "mg", "миллиграмм": "mg", "миллиграмма": "mg",
            "г": "g", "грамм": "g", "грамма": "g",
            "кг": "kg", "килограмм": "kg", "килограмма": "kg",
            "мл": "mL", "миллилитр": "mL", "миллилитра": "mL",
            "л": "L", "литр": "L",
            "мм рт.ст.": "mm Hg", "мм рт ст": "mm Hg", "мм.рт.ст.": "mm Hg",
            "мм": "mm", "миллиметр": "mm",
            "см": "cm", "сантиметр": "cm",
            "м": "m", "метр": "m",
            "мкм": "μm", "микрометр": "μm", "микрон": "μm",
            "уед": "U", "единиц": "U", "единицы": "U",
            "%": "%", "процент": "%",
            "уд/мин": "bpm", "ударов в минуту": "bpm",
            "°c": "°C", "градус цельсия": "°C",
        }
        if normalized in UNIT_MAP:
            return UNIT_MAP[normalized]
        return v


class Medication(BaseModel):
    """Medication information."""

    @model_validator(mode="before")
    @classmethod
    def remap_type_to_name(cls, data: Any) -> Any:
        """Remap 'type' field to 'name' if name is missing (LLM sometimes returns type)."""
        if isinstance(data, dict) and "name" not in data and "type" in data:
            data = dict(data)
            data["name"] = data.pop("type")
        return data

    name: str = Field(
        description="Medication name",
    )
    dosage: str | None = Field(
        default=None,
        description="Dosage (e.g., '500 mg', '10 ml')",
    )
    frequency: str | None = Field(
        default=None,
        description="Frequency (e.g., 'twice daily', 'morning')",
    )
    duration: str | None = Field(
        default=None,
        description="Course duration (e.g., '14 days', '1 month')",
    )
    route: str | None = Field(
        default=None,
        description="Administration route (e.g., 'oral', 'IM', 'topical')",
    )


class MedicalDoc(BaseModel):
    """Universal medical document schema.

    Stores the result of one PEC extraction step. The schema_id comes from the
    catalog and is resolved by the Planner before this model is constructed.
    LLM fills relevant fields; others remain empty.
    """

    # === IDENTIFICATION ===
    schema_id: str = Field(
        description="Document type determined by Planner. Must be a canonical schema id from the catalog.",
    )

    @model_validator(mode="before")
    @classmethod
    def ensure_schema_id(cls, data: Any) -> Any:
        """
        Ensure schema_id is present. If missing, set default to 'unknown' and log warning.
        """
        if isinstance(data, dict):
            if "schema_id" not in data or not data.get("schema_id"):
                log.warning("schema_id is missing or empty in MedicalDoc input; defaulting to 'unknown'. Input keys: %s", list(data.keys()))
                data["schema_id"] = "unknown"
        return data

    @field_validator("schema_id", mode="before")
    @classmethod
    def normalize_schema_id(cls, v: Any) -> str:
        """Validate schema_id against the catalog. Alias resolution is the catalog's responsibility."""
        from flows.pec.schema_catalog import default_catalog
        if v is None:
            log.warning("schema_id is None; defaulting to 'unknown'")
            return "unknown"
        if not isinstance(v, str):
            v = str(v)
        normalized = v.strip().lower()
        if not normalized:
            log.warning("schema_id is empty after normalization; defaulting to 'unknown'")
            return "unknown"
        if not default_catalog().has(normalized):
            log.warning("schema_id '%s' is not a known catalog id; defaulting to 'unknown'", normalized)
            return "unknown"
        return normalized

    # === COMMON SECTIONS ===
    document: DocumentInfo = Field(
        default_factory=DocumentInfo,
        description="Document metadata",
    )
    patient: PatientInfo = Field(
        default_factory=PatientInfo,
        description="Patient information",
    )

    # === MEASUREMENTS (lab, diagnostic) ===
    measurements: list[Measurement] = Field(
        default_factory=list,
        description=(
            "Numeric measurements: "
            "for lab - tests (hemoglobin, glucose); "
            "for diagnostic - organ sizes, volumes"
        ),
    )

    # === TEXT FINDINGS (diagnostic, consultation) ===
    findings: list[str] = Field(
        default_factory=list,
        description=(
            "Text findings and observations: "
            "ultrasound descriptions, examination results, complaints"
        ),
    )

    # === DIAGNOSES (consultation, diagnostic) ===
    diagnoses: list[str] = Field(
        default_factory=list,
        description="Diagnoses (primary and secondary)",
    )

    # === RECOMMENDATIONS (consultation, medication_trace) ===
    recommendations: list[str] = Field(
        default_factory=list,
        description="Doctor recommendations and follow-up instructions",
    )

    # === MEDICATIONS (medication_trace) ===
    medications: list[Medication] = Field(
        default_factory=list,
        description="Prescribed medications",
    )

    # === CONCLUSION (all types) ===
    conclusion: str | None = Field(
        default=None,
        description="Overall document conclusion or summary",
    )

    # === OPTIONAL FIELDS ===
    procedure_name: str | None = Field(
        default=None,
        description="Procedure or examination name",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Document tags and keywords",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    @field_validator("conclusion", mode="before")
    @classmethod
    def normalize_conclusion(cls, v: Any) -> str | None:
        """Convert dict to string if needed."""
        if v is None:
            return None
        if isinstance(v, dict):
            if "diagnosis" in v:
                return v["diagnosis"]
            return str(v)
        return str(v) if not isinstance(v, str) else v

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, v: Any) -> list[str]:
        return _normalize_to_list(v)

    @field_validator("findings", mode="before")
    @classmethod
    def normalize_findings(cls, v: Any) -> list[str]:
        return _normalize_to_list(v)

    @field_validator("diagnoses", mode="before")
    @classmethod
    def normalize_diagnoses(cls, v: Any) -> list[str]:
        return _normalize_to_list(v)

    @field_validator("recommendations", mode="before")
    @classmethod
    def normalize_recommendations(cls, v: Any) -> list[str]:
        return _normalize_to_list(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v: Any) -> list[str]:
        return _normalize_to_list(v)

    def merge(self, other: "MedicalDoc") -> "MedicalDoc":
        """Incremental merge. self = накопленный doc, other = результат нового шага.
        Возвращает новый объект, self/other не мутируются.
        """

        if self.schema_id != other.schema_id:
            log.warning(
                "Schema ID mismatch in MedicalDoc.merge: self=%s, other=%s, using self",
                self.schema_id, other.schema_id,
            )

        def _merge_scalar_fields(
            base: "DocumentInfo | PatientInfo | None",
            new: "DocumentInfo | PatientInfo | None",
            model_cls: type,
        ) -> "DocumentInfo | PatientInfo | None":
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

        def _dedup_by_name(
            items: list["Measurement | Medication"], key_fn
        ) -> list["Measurement | Medication"]:
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
            tags=_dedup_strings(self.tags + other.tags),
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
        default="",
        description="Extracted data as YAML (empty if skipped/failed)",
    )
    step_results: list[StepResult] = Field(
        default_factory=list,
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
