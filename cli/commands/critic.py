from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from flows.pec.build_pec import build_pec
from flows.pec.models import load_run_context, run_context_to_yaml, RunStatus

log = logging.getLogger("advisor.critic")


def critic(
    ctx: typer.Context,
    context_yaml: str,
) -> None:
    """Run the critic to validate all executed steps sequentially.
    
    This command reviews every step_result in context.steps_results in order,
    stopping at the first rejected step.
    """
    orchestrator = build_pec(
        llm_factory=ctx.obj["llm_factory"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )
    
    try:
        runCtx = load_run_context(Path(context_yaml))
        
        if runCtx.plan is None:
            log.error("Plan is not set in context")
            raise typer.Exit(code=2)
        
        if not runCtx.steps_results:
            log.error("No step results to review. Run 'exec' first.")
            raise typer.Exit(code=2)
        
        for sr in runCtx.steps_results:
            step = next((s for s in runCtx.plan.steps if s.id == sr.step_id), None)
            title = step.title if step else "unknown"
            log.info("Reviewing step %d: %s", sr.step_id, title)
        asyncio.run(orchestrator.critic(runCtx))
        
        if runCtx.status == RunStatus.FAILED:
            log.error("Review failed: %d issues found", len(runCtx.critic_feedback))
            raise typer.Exit(code=1)
        
        log.info("All steps approved")
        
    except Exception as e:
        log.exception("Review failed: %s", e)
        raise typer.Exit(code=2)
    
    typer.echo(run_context_to_yaml(runCtx), nl=False)
    raise typer.Exit(code=0)
