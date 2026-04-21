from __future__ import annotations

from llm.types import ChatRequest, Message
from orchestrator.models import ReviewResult, PlanStep, StepResult

from orchestrator.executors.base import BaseExecutor
from orchestrator.prompting.renderer import render_step_template, render_review_feedback

import logging

log = logging.getLogger(__name__)


class CodeExecutor(BaseExecutor):
  """
  Executes code-oriented steps.

  Responsibility:
  - interpret step as code task
  - call LLM with coding prompt
  - return structured result
  """

  async def execute(
      self,
      step: PlanStep,
      previous_results: str = "",
      review_feedback: ReviewResult | None = None,
  ) -> StepResult:
    log.debug("CodeExecutor.execute(step_id=%s, title=%r)", step.id, step.title)

    feedback_block = render_review_feedback(review_feedback)

    system_prompt = render_step_template(
      step,
      self._system_template,
      previous_results=previous_results,
    )
    user_prompt = render_step_template(
      step,
      self._user_template,
      previous_results=previous_results,
      review_feedback_block=feedback_block,
    )

    resp = await self._llm.chat(
      ChatRequest(
        model=self._model_name,
        messages=[
          Message(role="system", content=system_prompt),
          Message(role="user", content=user_prompt),
        ],
      )
    )

    log.debug("CodeExecutor got response (len=%d)", len(resp.text))

    return StepResult(
      id=step.id,
      executor="code",
      content=resp.text,
      assumptions=[],
    )
