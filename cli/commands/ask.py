from __future__ import annotations

import asyncio
import logging
import typer

from common.types import ChatRequest, Message


def ask(
    ctx: typer.Context,
    user_request: str,
) -> None:
    """
    CLI command: ask

    Purpose:
    - Direct LLM call without orchestration layer
    - Used for debugging prompts and model behavior
    """ 

    log = logging.getLogger("advisor.ask")

    llm_factory = ctx.obj["llm_factory"]
    models_registry = ctx.obj["models_registry"]
    ask_model = models_registry.models["default"].primary
    llm = llm_factory.for_model(ask_model)

    try:
        response = asyncio.run(
            llm.chat(
                ChatRequest(
                    messages=[
                        Message(role="user", content=user_request),
                    ],
                )
            )
        )
    except Exception as e:
        log.exception("LLM call failed: %s", e)
        raise typer.Exit(code=2)

    log.info("Response (model=%s): %s", response.model_alias or ask_model, response.text)

    raise typer.Exit(code=0)
