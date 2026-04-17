from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from flows.pec.executors.utils import summarize_previous_results
from flows.pec.models import PlanStep, StepResult
from llm.types import ChatRequest, Message
from tools.prompts import load_role_prompt, render_template

log = logging.getLogger(__name__)


class CodeExecutor:
    """
    CodeExecutor executes a single coding PlanStep using an LLM.

    Purpose:
    - Execute steps where the expected output is runnable code or code artifacts (functions,
      modules, tests, patches).
    - Use the role prompt stored on disk (prompts/code_executor.md) to enforce code-oriented output
      conventions (code fences, file headers, assumptions section, etc.).

    Inputs:
    - step: PlanStep (must contain title/input/output/success_criteria)
    - previous_results: prior StepResult list (used as context)

    Output:
    - StepResult with executor="code_executor" and content set to the model response text
      (typically code blocks + minimal additional text as required by prompt).

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
        log.debug("CodeExecutor.execute(step_id=%s, title=%r)", step.id, step.title)

        template = load_role_prompt("code_executor", prompts_dir=self._prompts_dir)

        prev = summarize_previous_results(previous_results, max_lines=20)

        values = {
            "STEP_TITLE": step.title,
            "STEP_INPUT": step.input,
            "STEP_OUTPUT": step.output,
            "STEP_SUCCESS_CRITERIA": "\n".join(f"- {c}" for c in step.success_criteria),
            "PREVIOUS_RESULTS": prev,
        }

        system_prompt = render_template(template, values)
        log.debug("CodeExecutor rendered system prompt (len=%d)", len(system_prompt))

        resp = await self._llm.chat(
            ChatRequest(
                model=self._model_alias,
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=step.input),
                ],
                # meta={"role": "code_executor"},
            )
        )

        log.debug("CodeExecutor got response (len=%d)", len(resp.text))

        return StepResult(
            step_id=step.id,
            executor="code_executor",
            content=resp.text,
            assumptions=[],
        )