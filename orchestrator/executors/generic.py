from __future__ import annotations

from llm.types import ChatRequest, Message
from orchestrator.models import PlanStep, StepResult

from orchestrator.executors.base import BaseExecutor
from orchestrator.prompting.renderer import render_step_template

import logging

log = logging.getLogger(__name__)


class GenericExecutor(BaseExecutor):
  """
  Executes general-purpose steps.

  Responsibility:
  - interpret step.input
  - call LLM
  - return structured StepResult
  """

  async def execute(self, step: PlanStep, previous_results: str = "") -> StepResult:
    system_prompt = render_step_template(
      step,
      self._system_template,
      previous_results=previous_results,
    )
    user_prompt = render_step_template(
      step,
      self._user_template,
      previous_results=previous_results,
    )

    log.debug("GenericExecutor.execute(step_id=%s, title=%r)", step.id, step.title)

    resp = await self._llm.chat(
      ChatRequest(
        model=self._model_name,
        messages=[
          Message(role="system", content=system_prompt),
          Message(role="user", content=user_prompt),
        ],
      )
    )

    log.debug("Executor got response (len=%d)", len(resp.text))

    return StepResult(
      step_id=step.id,
      executor="generic",
      content=resp.text,
      assumptions=[],
    )
