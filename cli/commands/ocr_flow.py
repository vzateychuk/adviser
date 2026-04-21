from __future__ import annotations

import asyncio
import logging

import typer

from flows.pec.build_pec import build_pec


def ocr_flow(
    ctx: typer.Context,
    file_path: str,
    doc_context: str = typer.Option("", "--context", "-c", help="Optional document context hint"),
) -> None:
    """Run the OCR PEC pipeline: Planner -> OcrExecutor -> Critic (retry loop)."""
    log = logging.getLogger("advisor.ocr_flow")

    orchestrator = build_pec(
        llm=ctx.obj["llm"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )

    try:
        result = asyncio.run(orchestrator.run(file_path, doc_context=doc_context))
    except Exception as e:
        log.exception("OCR flow failed: %s", e)
        raise typer.Exit(code=2)

    log.info(
        "OCR flow complete: schema=%r, retries=%d, steps=%d",
        result.schema_name,
        result.retry_count,
        len(result.step_results),
    )
    typer.echo(result.yaml_content)
    raise typer.Exit(code=0)
