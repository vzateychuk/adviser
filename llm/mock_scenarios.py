from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from common.types import ChatRequest, ChatResponse


T = TypeVar("T", bound=BaseModel)

MockScenario = Callable[[ChatRequest], ChatResponse]
StructuredMockScenario = Callable[[ChatRequest, type[T]], T]


def _last_user(req: ChatRequest) -> str:
    return next((m.content for m in reversed(req.messages) if m.role == "user"), "")


# =============================================================================
# LEGACY TEXT SCENARIOS (for backward compatibility with chat())
# =============================================================================


def planner_mock(req: ChatRequest) -> ChatResponse:
    user = _last_user(req).lower()
    if "not medical" in user or "shopping list" in user:
        return ChatResponse(
            text=(
                "action: SKIP\n"
                "goal: Input is not a medical document\n"
                "schema_name: null\n"
                "steps: []\n"
            )
        )
    text = _last_user(req)
    schema_name = "lab" if any(token in user for token in ["lab", "анализ", "blood", "hemoglobin"]) else "consultation"
    return ChatResponse(
        text=(
            "action: PLAN\n"
            "goal: Extract medical data from document\n"
            f"schema_name: {schema_name}\n"
            "  - deterministic test scenario\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Extract document data\n"
            "    type: ocr\n"
            f"    input: {schema_name}_document\n"
            f"    output: {schema_name}\n"
            "    success_criteria:\n"
            "      - all numeric values match the source\n"
            "      - all dates match the source\n"
            "      - all units match the source when present\n"
        )
    )


def ocr_executor_mock(req: ChatRequest) -> ChatResponse:
    user = _last_user(req).lower()
    if "active_schema: lab" in user:
        return ChatResponse(
            text=(
                "document:\n"
                "  date: '2024-01-01'\n"
                "  org: Mock Lab\n"
                "  source_ref: mock_document\n"
                "patient:\n"
                "  full_name: Mock Patient\n"
                "  surname: Patient\n"
                "  birth_date: null\n"
                "laboratory_panel:\n"
                "  results:\n"
                "    - analyte: Hemoglobin\n"
                "      value: '120'\n"
                "      unit: g/L\n"
                "      reference_range: 120-160\n"
            )
        )
    return ChatResponse(
        text=(
            "document:\n"
            "  date: '2024-01-01'\n"
            "patient:\n"
            "  full_name: Mock Patient\n"
            "consultation:\n"
            "  summary: Follow-up visit\n"
        )
    )


def critic_mock(req: ChatRequest) -> ChatResponse:
    return ChatResponse(text="approved: true\nsummary: Mock critic approval\nissues: []\n")


def default_mock(req: ChatRequest) -> ChatResponse:
    return ChatResponse(text=f"[MOCK] {_last_user(req)}")


# =============================================================================
# STRUCTURED SCENARIOS (for chat_structured())
# =============================================================================


def planner_structured_mock(req: ChatRequest, response_model: type[T]) -> T:
    """Return a pre-built PlannerOutputSchema for structured output tests.

    The response_model is passed so we can construct the correct type.
    We use lazy imports to avoid circular dependencies with flows.pec.models.
    """
    from flows.pec.models import StepType
    from flows.pec.planner import PlannerOutputSchema, PlanStepSchema

    user = _last_user(req).lower()

    # SKIP scenario
    if "not medical" in user or "shopping list" in user:
        result = PlannerOutputSchema(
            action="SKIP",
            goal="Input is not a medical document",
            schema_name=None,
            steps=[],
        )
        return result  # type: ignore[return-value]

    # PLAN scenario
    schema_name = "lab" if any(token in user for token in ["lab", "анализ", "blood", "hemoglobin"]) else "consultation"

    result = PlannerOutputSchema(
        action="PLAN",
        goal="Extract medical data from document",
        schema_name=schema_name,
        steps=[
            PlanStepSchema(
                id=1,
                title="Extract document data",
                type=StepType.OCR,
                input=f"{schema_name}_document",
                output=schema_name,
                success_criteria=[
                    "Preserve all dates exactly as written",
                    "Preserve all numeric values exactly as written",
                    "Preserve all measurement units exactly as written",
                ],
            )
        ],
    )
    return result  # type: ignore[return-value]


def executor_structured_mock(req: ChatRequest, response_model: type[T]) -> T:
    """Return a pre-built MedicalDoc for structured output tests.

    Determines schema_id from request content and returns sample data.
    """
    from flows.pec.models import (
        DocumentInfo, MedicalDoc, Measurement, Medication, PatientInfo,
    )

    user = _last_user(req).lower()

    # Determine schema_id from content
    if any(token in user for token in ["lab", "анализ", "blood", "hemoglobin", "glucose"]):
        schema_id = "lab"
        measurements = [
            Measurement(name="Hemoglobin", value="140", unit="g/L", status="normal"),
            Measurement(name="Glucose", value="5.2", unit="mmol/L", status="normal"),
        ]
        findings = []
        diagnoses = []
    elif any(token in user for token in ["diagnostic", "ultrasound", "узи", "imaging"]):
        schema_id = "diagnostic"
        measurements = [Measurement(name="Liver size", value="120", unit="mm", status="normal")]
        findings = ["Liver enlarged", "No focal lesions"]
        diagnoses = []
    elif any(token in user for token in ["medication", "medication_trace", "рецепт"]):
        schema_id = "medication_trace"
        measurements = []
        findings = []
        diagnoses = []
    else:
        schema_id = "consultation"
        measurements = []
        findings = ["Patient reports fatigue", "Physical exam unremarkable"]
        diagnoses = ["Fatigue, etiology TBD"]

    result = MedicalDoc(
        schema_id=schema_id,
        document=DocumentInfo(
            date="2024-01-01",
            organization="Mock Medical Center",
            doctor="Dr. Mock",
        ),
        patient=PatientInfo(
            full_name="Mock Patient",
            birth_date="1980-05-15",
            gender="unknown",
        ),
        measurements=measurements,
        findings=findings,
        diagnoses=diagnoses,
        recommendations=["Follow-up in 2 weeks"],
        medications=[
            Medication(name="Aspirin", dosage="500mg", frequency="once daily")
        ] if schema_id in ["consultation", "medication_trace"] else [],
        procedure_name="Mock Procedure" if schema_id == "diagnostic" else None,
        conclusion="Mock conclusion based on extraction",
    )
    return result  # type: ignore[return-value]


def critic_structured_mock(req: ChatRequest, response_model: type[T]) -> T:
    """Return a pre-built CriticResult for structured output tests."""
    from flows.pec.models import CriticResult

    result = CriticResult(
        approved=True,
        summary="Mock critic approval",
        issues=[],
    )
    return result  # type: ignore[return-value]


def default_structured_mock(req: ChatRequest, response_model: type[T]) -> T:
    """Fallback: construct a minimal valid instance of the response model."""
    # This is a best-effort fallback for unknown models
    # Real tests should provide specific scenarios
    raise NotImplementedError(
        f"No structured mock scenario for {response_model.__name__}. "
        "Add a specific scenario or use a text mock with JSON output."
    )
