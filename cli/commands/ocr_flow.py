from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from flows.pec.build_pec import build_pec



def ocr_flow(
    ctx: typer.Context,
    file_path: str,
    doc_context: str = typer.Option("", "--context", "-c", help="Optional inline document text/context"),
) -> None:
    """Run the full OCR pipeline end to end for a single document.

    This is the user-facing path when we want the orchestrator to plan, execute,
    and review in one continuous run.
    """

    log = logging.getLogger("advisor.ocr_flow")

    orchestrator = build_pec(
        llm_factory=ctx.obj["llm_factory"],
        app_cfg=ctx.obj["app_cfg"],
        models_registry=ctx.obj["models_registry"],
    )

    document_text = doc_context
    path = Path(file_path)
    if path.exists() and not document_text:
        document_text = path.read_text(encoding="utf-8")

    try:
        result = asyncio.run(orchestrator.run(file_path, doc_content=document_text))
    except Exception as e:
        log.exception("OCR flow failed: %s", e)
        raise typer.Exit(code=2)

    typer.echo(result.yaml_content)
    raise typer.Exit(code=0)
