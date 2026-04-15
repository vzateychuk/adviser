from __future__ import annotations

import asyncio
import logging

import typer

from llm.errors import LLMError
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from tools.prompts import load_role_prompt, render_template

log = logging.getLogger(__name__)


def ask(
    ctx: typer.Context,
    text: str,
    role: str = typer.Option("planner", "--role"),
) -> None:
    if not ctx.obj:
        raise RuntimeError(
            "CLI context is not initialized (ctx.obj is empty). Did you run via 'advisor ...'?"
        )

    llm: LLMClient = ctx.obj["llm"]
    models_registry = ctx.obj["models_registry"]

    try:
        model_alias = models_registry.models[role].primary
    except KeyError as e:
        raise typer.BadParameter(f"Unknown role: {role}") from e

    prompt_template = load_role_prompt(role)
    placeholder_values = {
            "STEP_TITLE": "",
            "STEP_INPUT": text,
            "STEP_OUTPUT": "",
            "STEP_SUCCESS_CRITERIA": "",
            "PREVIOUS_RESULTS": "",
    }
    system_prompt = render_template(prompt_template, placeholder_values)

    async def _run() -> None:
        try:
            resp = await llm.chat(
                ChatRequest(
                    model=model_alias,
                    messages=[
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=text),
                    ],
                )
            )
        except LLMError as e:
            log.error("LLM request failed (status=%s). Model='%s'. Details: %s", e.status_code, model_alias, e)
            raise typer.Exit(code=2)

        print(resp.text)

    asyncio.run(_run())