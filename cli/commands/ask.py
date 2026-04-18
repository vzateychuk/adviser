from __future__ import annotations

import asyncio
import logging
import typer

from llm.types import ChatRequest, Message


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

    llm = ctx.obj["llm"]

    try:
        response = asyncio.run(
            llm.chat(
                ChatRequest(
                    model="default",
                    messages=[
                        Message(role="user", content=user_request),
                    ],
                )
            )
        )
    except Exception as e:
        log.exception("LLM call failed: %s", e)
        raise typer.Exit(code=2)

    log.info("Response: %s", response.text)

    raise typer.Exit(code=0)