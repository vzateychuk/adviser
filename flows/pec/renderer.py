from __future__ import annotations

from typing import Any, Callable, Sequence
import json

from flows.pec.models import CriticIssue, CriticResult, MedicalDoc, PlanStep, RunContext, StepResult
from flows.pec.schema_catalog import SchemaDefinition
from tools.prompt import render_template


def render_step_template(
    context: RunContext,
    step: PlanStep,
    template: str,
    *,
    previous_results: str = "",
    critic_feedback: str = "",
    schema: SchemaDefinition | None = None,
) -> str:
    values = {
        "USER_REQUEST": context.user_request,
        "DOCUMENT_CONTENT": context.document_content,
        "ACTIVE_SCHEMA": context.active_schema or "",
        "STEP_TITLE": step.title,
        "STEP_INPUT": step.input,
        "STEP_OUTPUT": step.output,
        "STEP_SUCCESS_CRITERIA": "\n".join(step.success_criteria),
        "PREVIOUS_RESULTS": previous_results,
        "CRITIC_FEEDBACK": critic_feedback,
        "SCHEMA_ID": schema.schema_id if schema else (context.active_schema or ""),
        "SCHEMA_TITLE": schema.title or "" if schema else "",
        "SCHEMA_REQUIRED_BLOCKS": "\n".join(schema.required_blocks) if schema else "",
        "SCHEMA_CRITIC_RULES": "\n".join(schema.critic_rules) if schema else "",
        "SCHEMA_YAML": schema.prompt_excerpt if schema else "",
    }
    return render_template(template, values)


def render_planner_prompt(
    *,
    user_request: str,
    document_content: str,
    schema_catalog_summary: str,
    template: str,
) -> str:
    return render_template(
        template,
        {
            "USER_REQUEST": user_request,
            "DOCUMENT_CONTENT": document_content,
            "SCHEMA_CATALOG": schema_catalog_summary,
        },
    )


def render_critic_template(
    context: RunContext,
    step: PlanStep,
    result: StepResult,
    template: str,
    *,
    schema: SchemaDefinition | None = None,
) -> str:
    criteria_text = "\n".join(f"- {c}" for c in step.success_criteria)
    step_text = (
        f"title: {step.title}\n"
        f"type: {step.type}\n"
        f"input: {step.input}\n"
        f"expected_output: {step.output}\n"
    )
    step_result_json = result.doc.model_dump_json(indent=2) if result.doc else "{}"
    values = {
        "USER_REQUEST": context.user_request,
        "DOCUMENT_CONTENT": context.document_content,
        "ACTIVE_SCHEMA": context.active_schema or "",
        "STEP": step_text,
        "STEP_RESULT": step_result_json,
        "SUCCESS_CRITERIA": criteria_text,
        "CRITIC_FEEDBACK": format_critic_feedback_items(context.critic_feedback),
        "SCHEMA_YAML": schema.prompt_excerpt if schema else "",
        "SCHEMA_CRITIC_RULES": "\n".join(schema.critic_rules) if schema else "",
    }
    return render_template(template, values)


def format_critic_feedback(verdict: CriticResult, *, attempt: int) -> str:
    lines = [f"attempt: {attempt}", f"summary: {verdict.summary}", "issues:"]
    if not verdict.issues:
        lines.append("  []")
        return "\n".join(lines)
    for issue in verdict.issues:
        lines.extend(
            [
                f"  - severity: {issue.severity}",
                f"    description: {issue.description}",
                f"    suggestion: {issue.suggestion}",
            ]
        )
    return "\n".join(lines)


def format_critic_feedback_items(issues: Sequence[CriticIssue]) -> str:
    if not issues:
        return "[]"
    lines = ["issues:"]
    for issue in issues:
        lines.extend(
            [
                f"  - severity: {issue.severity}",
                f"    description: {issue.description}",
                f"    suggestion: {issue.suggestion}",
            ]
        )
    return "\n".join(lines)


def _safe_truncate(value: str, length: int = 80) -> str:
    """Обрезать строку до указанной длины с добавлением '...'."""
    return value[:length] + "..." if len(value) > length else value


def _format_list_count(items: list[Any], name_fn: Callable[[Any], str], max_show: int = 3) -> str | None:
    """Форматирует список как 'N items (name1, name2, ...)'. Возвращает None если список пуст."""
    if not items:
        return None
    names = ", ".join(name_fn(item) for item in items[:max_show])
    return f"{len(items)} item(s) ({names})"


def summarize_previous_results(doc: MedicalDoc | None, *, max_fields: int = 10) -> str:
    """Текстовое резюме уже извлечённых полей для промпта следующего шага.

    Приоритет полей (сверху вниз):
    1. schema_id
    2. patient.full_name, document.date, document.organization
    3. patient.birth_date, procedure_name, conclusion
    4. Counts списков (findings, diagnoses, recommendations, measurements, medications)
    5. Остальные скаляры (document.doctor, document.specialty, patient.gender)
    6. notes (в конце)
    """
    if doc is None:
        return ""

    # Декларативное описание полей: (path, extractor, formatter)
    # extractor возвращает None если поле не нужно показывать
    field_extractors: list[tuple[str, Callable[[], str | None], Callable[[str], str] | None]] = [
        # 1. schema_id (всегда)
        ("schema_id", lambda: doc.schema_id, None),
        # 2. Patient & Document core
        ("patient.full_name", lambda: doc.patient.full_name, None),
        ("document.date", lambda: doc.document.date, None),
        ("document.organization", lambda: doc.document.organization, None),
        # 3. More patient/document info
        ("patient.birth_date", lambda: doc.patient.birth_date, None),
        ("procedure_name", lambda: doc.procedure_name, None),
        ("conclusion", lambda: doc.conclusion, _safe_truncate),
        # 4. List counts
        ("findings", lambda: _format_list_count(doc.findings, lambda f: f) if doc.findings else None, None),
        ("diagnoses", lambda: _format_list_count(doc.diagnoses, lambda d: d) if doc.diagnoses else None, None),
        ("recommendations", lambda: _format_list_count(doc.recommendations, lambda r: r) if doc.recommendations else None, None),
        ("measurements", lambda: _format_list_count(doc.measurements, lambda m: m.name), None),
        ("medications", lambda: _format_list_count(doc.medications, lambda med: med.name), None),
        # 5. Other scalars
        ("document.doctor", lambda: doc.document.doctor, None),
        ("document.specialty", lambda: doc.document.specialty, None),
        ("patient.gender", lambda: doc.patient.gender, None),
        # 6. notes (в конце)
        ("notes", lambda: doc.notes, _safe_truncate),
    ]

    # Собираем только непустые поля
    output_lines: list[str] = []
    for path, extractor, formatter in field_extractors:
        value = extractor()
        if value is None:
            continue
        formatted = f"{path}: {formatter(value) if formatter else value}"
        output_lines.append(formatted)

    # Обрезка по max_fields
    if len(output_lines) > max_fields:
        output_lines = output_lines[:max_fields]

    return "Extracted so far:\n" + "\n".join(f"- {line}" for line in output_lines)
