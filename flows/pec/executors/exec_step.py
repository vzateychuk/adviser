from __future__ import annotations

import asyncio
import json
import logging

import typer

from flows.pec.executors.code_exec import CodeExecutor
from flows.pec.executors.generic_exec import GenericExecutor
from flows.pec.models import PlanStep, StepResult, StepType

log = logging.getLogger(__name__)


def exec_step(ctx: typer.Context, step_json: str) -> None:
    """
    Execute a single PlanStep provided as a JSON string and print StepResult.content.
    """
    if not ctx.obj:
        raise RuntimeError("CLI context is not initialized (ctx.obj is empty).")

    llm = ctx.obj["llm"]
    models_registry = ctx.obj["models_registry"]
    prompts_dir = ctx.obj["prompts_dir"]

    # Parse and validate step JSON into a PlanStep
    try:
        data = json.loads(step_json)
        step = PlanStep.model_validate(data)
    except Exception as e:
        raise typer.BadParameter(f"Invalid step JSON: {e}") from e

    async def _run() -> None:
        previous: list[StepResult] = []

        if step.type == StepType.CODE:
            model_alias = models_registry.models["code_executor"].primary
            ex = CodeExecutor(llm, model_alias=model_alias, prompts_dir=prompts_dir)
            log.debug("Selected CodeExecutor model=%s", model_alias)
        else:
            model_alias = models_registry.models["generic_executor"].primary
            ex = GenericExecutor(llm, model_alias=model_alias, prompts_dir=prompts_dir)
            log.debug("Selected GenericExecutor model=%s", model_alias)

        res = await ex.execute(step, previous_results=previous)
        print(res.content)

    asyncio.run(_run())