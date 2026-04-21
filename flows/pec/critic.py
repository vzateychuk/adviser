from __future__ import annotations

import json
import logging
import re

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from flows.pec.models import CriticResult, PlanStep, StepResult
from flows.pec.prompting.renderer import render_critic_template

log = logging.getLogger(__name__)

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


class Critic:
    """
    Critic — verifies OcrExecutor output against step success criteria.

    Responsibility:
    - call LLM with step context + execution result
    - parse and validate JSON verdict as CriticResult
    - return approved=True (accept) or approved=False (retry with issues)

    No orchestration logic. No retry decision — that belongs to PecOrchestrator.
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

    async def review(self, step: PlanStep, result: StepResult) -> CriticResult:
        """
        Review a single step result.

        Args:
            step: the PlanStep that was executed
            result: the StepResult produced by OcrExecutor

        Returns:
            CriticResult with approved verdict and optional issues list
        """
        user_content = render_critic_template(step, result, self._user_template)

        resp = await self._llm.chat(
            ChatRequest(
                model=self._model,
                messages=[
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_content),
                ],
            )
        )

        log.debug("Critic got response (len=%d)", len(resp.text))

        json_text = _extract_json(resp.text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            log.error("Critic returned non-JSON output. First 200 chars: %r", resp.text[:200])
            raise ValueError(f"Critic response is not valid JSON: {exc}") from exc

        return CriticResult.model_validate(data)
