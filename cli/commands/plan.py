from __future__ import annotations
import asyncio

import logging
import typer

from orchestrator.build_orchestrator import build_orchestrator

def plan(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """
    CLI command: plan

    Flow:
    1. Resolve dependencies from ctx.obj
    2. Build orchestrator
    3. Run planning + execution pipeline
    4. Print result
    """

    log = logging.getLogger("advisor.plan")

    llm = ctx.obj["llm"]
    app_cfg = ctx.obj["app_cfg"]
    models_registry = ctx.obj["models_registry"]

    orchestrator = build_orchestrator(
        llm=llm,
        app_cfg=app_cfg,
        models_registry=models_registry,
    )

    try:
        results = asyncio.run(orchestrator.run(user_request))
    except Exception as e:
        log.exception("Plan execution failed: %s", e)
        raise typer.Exit(code=2)

    for r in results:
        log.info("Step %s: %s", r.step_id, r.content)

    raise typer.Exit(code=0)