from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import typer
from flows.pec.build_pec import build_pec
from flows.pec.models import load_run_context, run_context_to_yaml, RunStatus

def exec(
    ctx: typer.Context,
    context_yaml: str,
) -> None:
    """Execute all steps using the executor WITHOUT critic validation.
    
    This command runs each step in the plan through the executor only,
    accumulating results in context.steps_results and printing the final
    context as YAML.
    
    Useful for:
    - Debugging the executor in isolation
    - Running extraction without validation
    """
    log = logging.getLogger("advisor.exec")
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
        if not runCtx.plan.steps:
            log.error("No steps in plan")
            raise typer.Exit(code=2)

        steps_list = runCtx.plan.steps
        log.info("Executing %d step(s)", len(steps_list))
        log.info("\n" + "\n".join(f"  [{i+1}] {s.title}" for i, s in enumerate(steps_list)))

        asyncio.run(orchestrator.execute(runCtx))
        log.info("All %d steps completed", len(runCtx.steps_results))
        
    except Exception as e:
        log.exception("Execution failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(run_context_to_yaml(runCtx), nl=False)
    raise typer.Exit(code=0)
