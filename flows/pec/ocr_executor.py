from __future__ import annotations

import logging

from flows.pec.models import MedicalDoc, RunContext, StepResult
from flows.pec.renderer import format_critic_feedback_items, render_step_template, summarize_previous_results
from llm.protocol import LLMClient
from common.types import ChatRequest, Message

log = logging.getLogger(__name__)


class OcrExecutor:
    """Runs the extraction step for a selected schema using chat_structured.

    Returns typed MedicalDoc via instructor validation. It only consumes RunContext
    data so retries can reuse the same state without hidden side effects or extra
    coupling to the CLI.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        system_prompt: str,
        user_template: str,
    ):
        self._llm = llm
        self._system_template = system_prompt
        self._user_template = user_template

    async def execute(self, context: RunContext, step_id: int) -> StepResult:
        """Execute one OCR extraction step and return the typed MedicalDoc result.

        The executor uses chat_structured to obtain a validated MedicalDoc
        matching the active schema.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for execution")
        step = next((item for item in context.plan.steps if item.id == step_id), None)
        if step is None:
            raise ValueError(f"Plan step not found: {step_id}")
        if not context.active_schema:
            raise ValueError("RunContext.active_schema is required for execution")

        previous_results = summarize_previous_results(context.doc)
        critic_feedback = format_critic_feedback_items(context.critic_feedback)

        system_prompt = render_step_template(
            context,
            step,
            self._system_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
        )
        user_prompt = render_step_template(
            context,
            step,
            self._user_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
        )

        log.debug("OcrExecutor.execute(step_id=%s, retry=%s)", step.id, bool(context.critic_feedback))
        doc = await self._llm.chat_structured(
            ChatRequest(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_prompt),
                ],
            ),
            response_model=MedicalDoc,
        )
        log.debug("OcrExecutor response doc: schema_id=%s", doc.schema_id)

        return StepResult(
            step_id=step.id,
            executor="ocr",
            doc=doc,
            assumptions=[],
        )
