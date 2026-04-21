from __future__ import annotations

from flows.pec.models import CriticResult, PlanStep, StepResult
from tools.prompt import render_template
from typing import Sequence


def render_step_template(
    step: PlanStep,
    template: str,
    previous_results: str = "",
    critic_feedback: str = "",
) -> str:
    """Render an executor step template using PlanStep fields."""
    values = {
        "STEP_TITLE": step.title,
        "STEP_INPUT": step.input,
        "STEP_OUTPUT": step.output,
        "STEP_SUCCESS_CRITERIA": "\n".join(step.success_criteria),
        "PREVIOUS_RESULTS": previous_results,
        "CRITIC_FEEDBACK": critic_feedback,
    }
    return render_template(template, values)


def render_critic_template(
    step: PlanStep,
    result: StepResult,
    template: str,
) -> str:
    """Render the Critic user prompt template."""
    criteria_text = "\n".join(f"- {c}" for c in step.success_criteria)
    step_text = (
        f"title: {step.title}\n"
        f"type: {step.type}\n"
        f"input: {step.input}\n"
        f"expected_output: {step.output}\n"
    )
    values = {
        "STEP": step_text,
        "STEP_RESULT": result.content,
        "SUCCESS_CRITERIA": criteria_text,
    }
    return render_template(template, values)


def format_critic_feedback(verdict: CriticResult, *, attempt: int) -> str:
    """Format CriticResult issues into a compact text block for executor retry."""
    lines = [f"[Critic feedback — attempt {attempt}] {verdict.summary}"]
    for issue in verdict.issues:
        lines.append(f"  [{issue.severity.upper()}] {issue.description} => {issue.suggestion}")
    return "\n".join(lines)

def summarize_previous_results(previous_results: Sequence[StepResult], *, max_lines: int = 20) -> str:
  """
  Build a compact text summary of previous step results to be inserted into prompts.

  Current behavior:
  - For each result, include a header line (step_id, executor)
  - Include only the first `max_lines` lines of the result content

  TODO:
  - Replace truncation-by-lines with a smarter summarizer:
    * extract structured artifacts (e.g. file names, function names)
    * prefer explicit "key findings" section to reduce lost-in-the-middle
    * optionally compress via a dedicated summarizer model
  """
  parts: list[str] = []

  for r in previous_results:
    lines = (r.content or "").splitlines()

    snippet = "\n".join(lines[:max_lines]).strip()

    parts.append(
      f"[step_id={r.step_id} executor={r.executor}]\n"
      f"OUTPUT:\n{snippet}"
    )

  return "\n\n".join(parts).strip()
