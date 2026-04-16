from __future__ import annotations

from typing import Sequence

from flows.pec.models import StepResult


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
        header = f"[step_id={r.step_id} executor={r.executor}]"
        lines = (r.content or "").splitlines()
        snippet = "\n".join(lines[:max_lines]).strip()
        parts.append(f"{header}\n{snippet}".strip())

    return "\n\n".join(parts).strip()