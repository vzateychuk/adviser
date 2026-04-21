from __future__ import annotations

import asyncio
import logging
import re

import typer

from llm.types import ChatRequest, Message
from tools.prompt import load_role_prompts
from flows.pec.planner import Planner

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def plan(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """
    Debug command: call Planner and print the resulting plan.

    Does NOT execute steps — useful for verifying Planner output for a document.
    """
    log = logging.getLogger("advisor.plan")

    llm = ctx.obj["llm"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

    planner_model = models_registry.models["planner"].primary
    system_prompt, _ = load_role_prompts("planner", prompts_dir=app_cfg.prompts_dir)

    planner = Planner(llm=llm, model=planner_model, prompt=system_prompt)

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