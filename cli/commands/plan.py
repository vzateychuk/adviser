from __future__ import annotations

import asyncio
import logging

import typer

from tools.prompt import load_role_prompts
from flows.pec.planner import Planner


def plan(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """
    Debug command: call Planner and print the resulting plan.

    Does NOT execute steps — useful for verifying Planner output for a document.
    """
    log = logging.getLogger("advisor.plan")

    llm_factory = ctx.obj["llm_factory"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

    planner_model = models_registry.models["planner"].primary
    system_prompt, _ = load_role_prompts("planner", prompts_dir=app_cfg.prompts_dir)
    planner_llm = llm_factory.for_model(planner_model)

    planner = Planner(llm=planner_llm, prompt=system_prompt)

    try:
        result = asyncio.run(planner.plan(user_request))
    except Exception as e:
        log.exception("Planner failed: %s", e)
        raise typer.Exit(code=2)

    log.info("Goal: %s", result.goal)
    log.info("Schema: %s", result.schema_name)
    for step in result.steps:
        log.info("  Step %d [%s]: %s", step.id, step.type, step.title)

    raise typer.Exit(code=0)