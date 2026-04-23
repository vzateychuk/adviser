from __future__ import annotations

import logging

from flows.pec.models import CriticResult, RunContext, StepResult
from flows.pec.renderer import render_critic_template
from flows.pec.schema_catalog import SchemaCatalog
from flows.pec.yaml_utils import load_llm_yaml
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message

log = logging.getLogger(__name__)


class Critic:
    """Reviews executor output against the current step and schema contract.

    The critic catches missing medical fields, altered values, and schema drift
    before the orchestrator accepts a result as final.
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
        self._system_prompt = system_prompt
        self._user_template = user_template
        self._schema_catalog = schema_catalog

    async def review(self, context: RunContext, step_id: int, result: StepResult) -> CriticResult:
        """Ask the LLM for a structured verdict on one executor result.

        This centralizes review behavior so retries and rejection reasons stay
        consistent across the orchestrator and debug CLI commands.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for review")
        step = next((item for item in context.plan.steps if item.id == step_id), None)
        if step is None:
            raise ValueError(f"Plan step not found: {step_id}")
        schema = self._schema_catalog.get(context.active_schema) if context.active_schema else None
        user_content = render_critic_template(
            context,
            step,
            result,
            self._user_template,
            schema=schema,
        )

        resp = await self._llm.chat(
            ChatRequest(
                messages=[
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_content),
                ],
            )
        )
        log.debug("Critic response text:\n%s", resp.text)
        data = load_llm_yaml(resp.text)
        return CriticResult.model_validate(data)
