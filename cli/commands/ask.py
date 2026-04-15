from __future__ import annotations

import asyncio
import typer

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message


def ask(
    ctx: typer.Context,
    text: str,
    role: str = typer.Option("planner", "--role"),
) -> None:
    if not ctx.obj:
        raise RuntimeError("CLI context is not initialized (ctx.obj is empty). Did you run via 'advisor ...'?")

    llm: LLMClient = ctx.obj["llm"]

    models_registry = ctx.obj["models_registry"]
    try:
        model_alias = models_registry.models[role].primary
    except KeyError as e:
        raise typer.BadParameter(f"Unknown role: {role}") from e

    async def _run() -> None:
        resp = await llm.chat(
            ChatRequest(
                model=model_alias,
                messages=[Message(role="user", content=text)],
            )
        )
        print(resp.text)

    asyncio.run(_run())