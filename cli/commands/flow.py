from __future__ import annotations

import asyncio
import logging

import typer

from orchestrator.build_orchestrator import build_orchestrator


def flow(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """Run user request through the full Planner -> Executor -> Critic pipeline."""
    log = logging.getLogger("advisor.flow")

    orchestrator = build_orchestrator(
        llm=ctx.obj["llm"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )

    try:
        result = asyncio.run(orchestrator.run(user_request))
    except Exception as e:
        log.exception("Flow failed: %s", e)
        raise typer.Exit(code=2)

    log.info("Flow status: `%s`", result.status)
    for step in result.step_results:
      log.info("Step id:`%s`, result: `%s`", step.id, step.content)

    raise typer.Exit(code=0)
