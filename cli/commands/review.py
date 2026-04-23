from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from flows.pec.build_pec import build_pec
from flows.pec.models import load_run_context, run_context_to_yaml



def review(
    ctx: typer.Context,
    context_yaml: str,
) -> None:
    """Run the critic stage from an existing RunContext YAML file.

    Separate review entry points make it easier to inspect rejection reasons and
    iterate on extraction quality.
    """

    log = logging.getLogger("advisor.review")
    orchestrator = build_pec(
        llm_factory=ctx.obj["llm_factory"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )

    try:
        context = load_run_context(Path(context_yaml))
        context = asyncio.run(orchestrator.review_context(context))
    except Exception as e:
        log.exception("Review failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(run_context_to_yaml(context), nl=False)
    raise typer.Exit(code=0)
