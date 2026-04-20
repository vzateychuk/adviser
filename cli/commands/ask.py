from __future__ import annotations

import asyncio
import logging

import typer

from orchestrator.executors.generic import GenericExecutor
from orchestrator.models import PlanStep, StepType
from tools.prompt import load_role_prompts


def ask(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """Call the generic executor for a single ask step.

    TODO: Replace with Clarifier sub-agent — a dedicated conversational agent
          that chats with the user to clarify intent before routing to the
          main pipeline. Current implementation is a temporary placeholder
          that routes directly to GenericExecutor without any clarification.
    """
    log = logging.getLogger("advisor.ask")

    llm = ctx.obj["llm"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

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

    step = PlanStep(
        id=1,
        title=user_request[:80],
        type=StepType.GENERIC,
        input=user_request,
        output="answer",
        success_criteria=["Addresses the user request"],
    )

    try:
        result = asyncio.run(executor.execute(step))
    except Exception as e:
        log.exception("Ask failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(result.content)
    raise typer.Exit(code=0)
