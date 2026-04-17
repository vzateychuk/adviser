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
    role: str = typer.Option("generic_executor", "--role"),
) -> None:
    """
    One-shot LLM call using the role prompt loaded from prompts/<role>.md
    and the model alias selected for that role from models.yaml.

    Default role is generic_executor to behave like a general assistant.
    """
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

    prompts_dir = ctx.obj["prompts_dir"]
    prompt_template = load_role_prompt(role, prompts_dir=prompts_dir)

    # Best-effort placeholder values for current stage.
    # We fill common keys to reduce unresolved-placeholder warnings across different prompts.
    placeholder_values = {
        # planner.md
        "USER_REQUEST": text,
        # critic.md
        "STEP": text,
        "STEP_RESULT": "",
        "SUCCESS_CRITERIA": "",
        # generic_executor.md / code_executor.md
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
                    meta={"role": role},
                )
            )
        except LLMError as e:
            log.error("LLM request failed. Model='%s'. Details: %s", model_alias, e)
            raise typer.Exit(code=2) from e

        typer.echo(resp.text)

    asyncio.run(_run())