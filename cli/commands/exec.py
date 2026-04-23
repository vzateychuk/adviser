from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from flows.pec.build_pec import build_pec
from flows.pec.models import load_run_context, run_context_to_yaml



def exec_stage(
    ctx: typer.Context,
    context_yaml: str,
) -> None:
    """Run the extraction stage from an existing RunContext YAML file.

    This isolates executor behavior so prompt and schema issues can be debugged
    without rerunning planner logic.
    """

    log = logging.getLogger("advisor.exec")
    orchestrator = build_pec(
        llm_factory=ctx.obj["llm_factory"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )

    try:
        context = load_run_context(Path(context_yaml))
        asyncio.run(orchestrator.execute(context))
    except Exception as e:
        log.exception("Execution failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(run_context_to_yaml(context), nl=False)
    raise typer.Exit(code=0)
