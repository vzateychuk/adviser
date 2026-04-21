# orchestrator/reviewer.py
from __future__ import annotations

import re
import logging

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from orchestrator.models import ReviewResult, PlanStep, StepResult
from tools.prompt import render_template

log = logging.getLogger(__name__)

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
  m = _FENCED_JSON_RE.search(text)
  if m:
    return m.group(1).strip()
  return text.strip()


class Reviewer:
  """
  Reviewer — reviews executor output against step success criteria.

  Responsibilities:
  - render reviewer prompts
  - call LLM
  - parse and return ReviewResult

  No orchestration logic. No retry logic.
  """

  def __init__(
      self,
      *,
      llm: LLMClient,
      model: str,
      system_prompt: str,
      user_template: str,
  ):
    self._llm = llm
    self._model = model
    self._system_prompt = system_prompt
    self._user_template = user_template

  async def review(self, step: PlanStep, result: StepResult) -> ReviewResult:
    """
    Review executor output for a single step.

    Args:
        step: the PlanStep that was executed
        result: StepResult returned by the executor

    Returns:
        ReviewResult with approved/rejected verdict and issues
    """
    step_text = (
      f"id: {step.id}\n"
      f"title: {step.title}\n"
      f"input: {step.input}\n"
      f"expected_output: {step.output}"
    )

    user_prompt = render_template(
      self._user_template,
      {
        "STEP": step_text,
        "STEP_RESULT": result.content,
        "SUCCESS_CRITERIA": "\n".join(step.success_criteria),
      },
    )

    log.debug("Reviewer.review(step_id=%s, title=%r)", step.id, step.title)

    resp = await self._llm.chat(
      ChatRequest(
        model=self._model,
        messages=[
          Message(role="system", content=self._system_prompt),
          Message(role="user", content=user_prompt),
        ],
      )
    )

    log.debug("Reviewer response (%s)", resp.text)

    json_text = _extract_json(resp.text)
    return ReviewResult.model_validate_json(json_text)
