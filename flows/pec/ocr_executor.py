from __future__ import annotations

import logging

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from flows.pec.models import PlanStep, StepResult
from flows.pec.renderer import render_step_template

log = logging.getLogger(__name__)


class OcrExecutor:
    """
    Executes OCR extraction steps.

    Responsibility:
    - receive a PlanStep describing document path + expected YAML schema
    - call a specialized OCR/vision LLM model
    - return StepResult with YAML-structured extracted data

    On Critic rejection the executor receives critic_feedback and retries
    the extraction, using feedback as additional context in the prompt.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        model_name: str,
        system_prompt: str,
        user_template: str,
    ):
        self._llm = llm
        self._model_name = model_name
        self._system_template = system_prompt
        self._user_template = user_template

    async def execute(
        self,
        step: PlanStep,
        previous_results: str = "",
        critic_feedback: str = "",
    ) -> StepResult:
        log.debug("OcrExecutor.execute(step_id=%s, title=%r, retry=%s)", step.id, step.title, bool(critic_feedback))

        system_prompt = render_step_template(
            step,
            self._system_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
        )
        user_prompt = render_step_template(
            step,
            self._user_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
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

        log.debug("OcrExecutor got response (len=%d)", len(resp.text))

        return StepResult(
            step_id=step.id,
            executor="ocr",
            content=resp.text,
            assumptions=[],
        )
