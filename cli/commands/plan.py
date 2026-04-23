from __future__ import annotations

import asyncio
import logging

import typer

from cli.commands.pec_context import build_initial_context
from flows.pec.build_pec import build_pec
from flows.pec.models import run_context_to_yaml



def plan(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """Run the planner stage only and print the resulting RunContext as YAML.

    This is useful for debugging triage and schema selection without spending
    time on extraction or review.
    """

    log = logging.getLogger("advisor.plan")
    orchestrator = build_pec(
        llm_factory=ctx.obj["llm_factory"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )
    context = build_initial_context(user_request)

    try:
        context = asyncio.run(orchestrator.plan(context))
    except Exception as e:
        log.exception("Planner failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(run_context_to_yaml(context), nl=False)
    raise typer.Exit(code=0)
