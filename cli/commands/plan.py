from __future__ import annotations

import asyncio
import logging

import typer

from orchestrator.planner import Planner
from tools.prompt import load_role_prompts


def plan(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """Call the Planner role to plan a user request."""
    log = logging.getLogger("advisor.plan")

    llm = ctx.obj["llm"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

    model_name = models_registry.models["planner"].primary
    system_prompt, user_template = load_role_prompts(
        "planner", prompts_dir=app_cfg.prompts_dir
    )

    planner = Planner(
        llm=llm,
        model=model_name,
        system_prompt=system_prompt,
        user_template=user_template,
    )

    try:
        result = asyncio.run(planner.plan(user_request, attempt=0))
    except Exception as e:
        log.exception("Planning failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(f"Goal: {result.goal}")
    for step in result.steps:
        typer.echo(f"Step {step.id}: {step.title}")
        log.debug("  type=%s input=%r", step.type, step.input)

    raise typer.Exit(code=0)
