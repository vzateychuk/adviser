from __future__ import annotations

import asyncio
import logging
import typer

from orchestrator.build_orchestrator import build_orchestrator


def ask(
    ctx: typer.Context,
    user_request: str,
) -> None:
  """Run user request through the full Planner → Executor → Critic pipeline."""

  log = logging.getLogger("advisor.ask")

  orchestrator = build_orchestrator(
    llm=ctx.obj["llm"],
    app_cfg=ctx.obj["app_cfg"],
    models_registry=ctx.obj["models_registry"],
  )

  try:
    result = asyncio.run(orchestrator.run(user_request))
  except Exception as e:
    log.exception("Orchestrator failed: %s", e)
    raise typer.Exit(code=2)

  for step in result.step_results:
    typer.echo(step.content)

  raise log.info("Result: `%s`", result)