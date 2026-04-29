from __future__ import annotations

import logging

from flows.pec.models import CriticResult, RunContext
from flows.pec.renderer import render_critic_final_template
from llm.protocol import LLMClient
from common.types import ChatRequest, Message

log = logging.getLogger(__name__)


class Critic:
    """Reviews the final merged document against the plan and success criteria.

    The critic catches missing medical fields, altered values, and schema drift
    before the orchestrator accepts a result as final.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        system_prompt: str,
        user_template: str,
    ):
        self._llm = llm
        self._system_prompt = system_prompt
        self._user_template = user_template

    async def review(self, context: RunContext) -> CriticResult:
        """Ask the LLM for a structured verdict on the final merged document.

        This centralizes review behavior so retries and rejection reasons stay
        consistent across the orchestrator and debug CLI commands.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for review")
        if context.doc is None:
            raise ValueError("RunContext.doc is required for review")

        user_content = render_critic_final_template(context, self._user_template)

        return await self._llm.chat_structured(
            ChatRequest(
                messages=[
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_content),
                ],
            ),
            response_model=CriticResult,
        )
