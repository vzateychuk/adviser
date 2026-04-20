from __future__ import annotations

from orchestrator.models import PlanStep, StepResult, CriticResult
from tools.prompt import render_template
from typing import Sequence

def render_step_template(
    step: PlanStep,
    template: str,
    previous_results: str = "",
    critic_feedback_block: str = "",
) -> str:
    """Render a step template using the structured PlanStep fields."""
    values = {
        "STEP_TITLE": step.title,
        "STEP_INPUT": step.input,
        "STEP_OUTPUT": step.output,
        "STEP_SUCCESS_CRITERIA": "\n".join(step.success_criteria),
        "PREVIOUS_RESULTS": previous_results,
        "CRITIC_FEEDBACK_BLOCK": critic_feedback_block,
    }
    return render_template(template, values)

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
      f"[step_id={r.id} executor={r.executor}]\n"
      f"OUTPUT:\n{snippet}"
    )

  return "\n\n".join(parts).strip()

def render_critic_feedback(feedback: CriticResult | None, *, attempt: int = 0) -> str:
  """
  Render CriticResult as an XML block for injection into Planner's user prompt.

  Returns empty string on first run (no feedback yet).
  """
  if feedback is None:
    return ""

  issues_xml = "\n".join(
    f'    <issue severity="{issue.severity}">\n'
    f"      <description>{issue.description}</description>\n"
    f"      <suggestion>{issue.suggestion}</suggestion>\n"
    f"    </issue>"
    for issue in feedback.issues
  )

  return (
    f'\n<critic_feedback attempt="{attempt}">\n'
    f"  <summary>{feedback.summary}</summary>\n"
    f"  <issues>\n{issues_xml}\n  </issues>\n"
    f"</critic_feedback>"
  )