from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from flows.pec.models import PlanStep, StepResult
from llm.types import ChatRequest, Message
from tools.prompts import load_role_prompt, render_template
from flows.pec.executors.utils import summarize_previous_results

log = logging.getLogger(__name__)


class GenericExecutor:
    """
    GenericExecutor executes a single non-coding PlanStep using an LLM.

    Purpose:
    - Execute steps where the expected output is primarily natural language (summaries, checklists,
      reasoning, explanations, etc.), not runnable code.
    - Use the role prompt stored on disk (prompts/generic_executor.md) to structure the LLM input.

    Inputs:
    - step: PlanStep (must contain title/input/output/success_criteria)
    - previous_results: prior StepResult list (used as context)

    Output:
    - StepResult with executor="generic_executor" and content set to the model response text.

    Notes:
    - This class is vendor-agnostic: it depends only on LLMClient + internal Message/ChatRequest types.
    - model selection is injected via model_alias (from models.yaml).
    - prompts_dir is injected via app.yaml to avoid reliance on current working directory.
    """

    def __init__(self, llm, *, model_alias: str, prompts_dir: Path) -> None:
        self._llm = llm
        self._model_alias = model_alias
        self._prompts_dir = prompts_dir

    async def execute(self, step: PlanStep, *, previous_results: Sequence[StepResult]) -> StepResult:
        log.debug("GenericExecutor.execute(step_id=%s, title=%r)", step.id, step.title)

        template = load_role_prompt("generic_executor", prompts_dir=self._prompts_dir)

        prev = summarize_previous_results(previous_results, max_lines=20)

        values = {
            "STEP_TITLE": step.title,
            "STEP_INPUT": step.input,
            "STEP_OUTPUT": step.output,
            "STEP_SUCCESS_CRITERIA": "\n".join(f"- {c}" for c in step.success_criteria),
            "PREVIOUS_RESULTS": prev,
        }

        system_prompt = render_template(template, values)
        log.debug("GenericExecutor rendered system prompt (len=%d)", len(system_prompt))

        resp = await self._llm.chat(
            ChatRequest(
                model=self._model_alias,
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=step.input),
                ],
                # meta={"role": "generic_executor"},
            )
        )

        log.debug("GenericExecutor got response (len=%d)", len(resp.text))

        return StepResult(
            step_id=step.id,
            executor="generic_executor",
            content=resp.text,
            assumptions=[],
        )