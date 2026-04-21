from __future__ import annotations

import re

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from orchestrator.models import PlanResult, ReviewResult
from orchestrator.prompting.renderer import render_review_feedback
from tools.prompt import render_template

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


class Planner:
    """
    Planner.

    Responsibility:
    - Convert user request -> structured PlanResult
    - Call LLM
    - Validate + parse JSON output

    No orchestration logic.
    No routing.
    No persistence.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        model: str,
        system_prompt: str,
        user_template: str,
    ):
        self.llm = llm
        self.model = model
        self.system_prompt = system_prompt
        self.user_template = user_template

    async def plan(
        self,
        user_request: str,
        review_feedback: ReviewResult | None = None,
        *,
        attempt: int = 0,
    ) -> PlanResult:
        """
        Calls LLM and parses structured PlanResult.

        On retry, injects review feedback into the user prompt so the planner
        can address the issues in the new plan.
        """
        user_content = render_template(
            self.user_template,
            {
                "USER_REQUEST": user_request,
                "REVIEW_FEEDBACK_BLOCK": render_review_feedback(
                    review_feedback, attempt=attempt
                ),
            },
        )

        resp = await self.llm.chat(
            ChatRequest(
                model=self.model,
                messages=[
                    Message(role="system", content=self.system_prompt),
                    Message(role="user", content=user_content),
                ],
            )
        )

        json_text = _extract_json(resp.text)
        return PlanResult.model_validate_json(json_text)