from __future__ import annotations

import logging

from flows.pec.models import RunContext, StepResult
from flows.pec.renderer import format_critic_feedback_items, render_step_template, summarize_previous_results
from flows.pec.schema_catalog import SchemaCatalog
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message

log = logging.getLogger(__name__)


class OcrExecutor:
    """Runs the extraction step for a selected schema using the current context.

    It only consumes RunContext data so retries can reuse the same state without
    hidden side effects or extra coupling to the CLI.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        system_prompt: str,
        user_template: str,
        schema_catalog: SchemaCatalog,
    ):
        self._llm = llm
        self._system_template = system_prompt
        self._user_template = user_template
        self._schema_catalog = schema_catalog

    async def execute(self, context: RunContext, step_id: int) -> StepResult:
        """Execute one OCR extraction step and return the raw YAML result.

        The executor does not interpret the result; it simply produces output that
        the critic can verify against the plan and the source document.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for execution")
        step = next((item for item in context.plan.steps if item.id == step_id), None)
        if step is None:
            raise ValueError(f"Plan step not found: {step_id}")
        if not context.active_schema:
            raise ValueError("RunContext.active_schema is required for execution")

        schema = self._schema_catalog.get(context.active_schema)
        previous_results = summarize_previous_results(context.steps_results)
        critic_feedback = format_critic_feedback_items(context.critic_feedback)

        system_prompt = render_step_template(
            context,
            step,
            self._system_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
            schema=schema,
        )
        user_prompt = render_step_template(
            context,
            step,
            self._user_template,
            previous_results=previous_results,
            critic_feedback=critic_feedback,
            schema=schema,
        )

        log.debug("OcrExecutor.execute(step_id=%s, retry=%s)", step.id, bool(context.critic_feedback))
        resp = await self._llm.chat(
            ChatRequest(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_prompt),
                ],
            )
        )
        log.debug("OcrExecutor response text:\n%s", resp.text)

        return StepResult(
            step_id=step.id,
            executor="ocr",
            content=resp.text.strip(),
            assumptions=[],
        )
