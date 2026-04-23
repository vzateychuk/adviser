from __future__ import annotations

from typing import Sequence

from flows.pec.models import CriticIssue, CriticResult, PlanStep, RunContext, StepResult
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
    values = {
        "USER_REQUEST": context.user_request,
        "DOCUMENT_CONTENT": context.document_content,
        "ACTIVE_SCHEMA": context.active_schema or "",
        "STEP": step_text,
        "STEP_RESULT": result.content,
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


def summarize_previous_results(previous_results: Sequence[StepResult], *, max_lines: int = 20) -> str:
    parts: list[str] = []
    for r in previous_results:
        lines = (r.content or "").splitlines()
        snippet = "\n".join(lines[:max_lines]).strip()
        parts.append(f"[step_id={r.step_id} executor={r.executor}]\nOUTPUT:\n{snippet}")
    return "\n\n".join(parts).strip()
