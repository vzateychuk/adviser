from __future__ import annotations

import asyncio
import json
import logging

import typer

from orchestrator.executors.code import CodeExecutor
from orchestrator.executors.generic import GenericExecutor
from orchestrator.models import PlanStep
from orchestrator.router import ExecutorRouter
from tools.prompt import load_role_prompts


def exec_step(
    ctx: typer.Context,
    step_json: str,
) -> None:
    """Execute a single plan step via the routed executor."""
    log = logging.getLogger("advisor.exec")

    llm = ctx.obj["llm"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

    try:
        step = PlanStep.model_validate(json.loads(step_json))
    except Exception as e:
        raise typer.BadParameter(f"Invalid step_json: {e}") from e

    router = ExecutorRouter()
    executor_type = router.route(step)

    if executor_type == "generic":
        model_name = models_registry.models["generic_executor"].primary
        system_prompt, user_template = load_role_prompts(
            "generic_executor", prompts_dir=app_cfg.prompts_dir
        )
        executor = GenericExecutor(
            llm=llm,
            model_name=model_name,
            system_prompt=system_prompt,
            user_template=user_template,
        )
    elif executor_type == "code":
        model_name = models_registry.models["code_executor"].primary
        system_prompt, user_template = load_role_prompts(
            "code_executor", prompts_dir=app_cfg.prompts_dir
        )
        executor = CodeExecutor(
            llm=llm,
            model_name=model_name,
            system_prompt=system_prompt,
            user_template=user_template,
        )
    else:
        raise typer.BadParameter(f"Unsupported executor type: {executor_type}")

    try:
        result = asyncio.run(executor.execute(step))
    except Exception as e:
        log.exception("Exec step failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(result.content)
    raise typer.Exit(code=0)
