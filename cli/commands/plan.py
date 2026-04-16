from __future__ import annotations

import asyncio
import json
import logging
import re

import typer

from flows.pec.models import PlanResult
from llm.errors import LLMError
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from tools.prompts import load_role_prompt, render_template

log = logging.getLogger(__name__)

# Matches ```json { ... } ``` (and also ``` { ... } ```)
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """
    Best-effort JSON extractor.

    Many models wrap JSON in markdown code fences (```json ... ```).
    This helper extracts the JSON object if a fenced block is present,
    otherwise returns the stripped original text.
    """
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def plan(
    ctx: typer.Context,
    text: str,
) -> None:
    """
    Calls the Planner prompt, expects a JSON plan, parses it and validates against PlanResult.

    Prints: 'Plan OK, steps=N' on success.

    Note: This is not a chat command. The planner is expected to return JSON only.
    """
    if not ctx.obj:
        raise RuntimeError("CLI context is not initialized (ctx.obj is empty).")

    llm: LLMClient = ctx.obj["llm"]
    models_registry = ctx.obj["models_registry"]

    role = "planner"
    model_alias = models_registry.models[role].primary

    prompts_dir = ctx.obj["prompts_dir"]
    prompt_template = load_role_prompt(role, prompts_dir=prompts_dir)
    system_prompt = render_template(prompt_template, {"USER_REQUEST": text})

    async def _run() -> None:
        try:
            resp = await llm.chat(
                ChatRequest(
                    model=model_alias,
                    messages=[
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=text),
                    ],
                    meta={"role": "planner"},
                )
            )
        except LLMError as e:
            log.error("Planner request failed. Model='%s'. Details: %s", model_alias, e)
            raise typer.Exit(code=2) from e

        json_text = _extract_json(resp.text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            log.error(
                "Planner returned non-JSON output. First 200 chars: %r",
                resp.text[:200],
            )
            raise typer.Exit(code=2) from e

        try:
            plan_obj = PlanResult.model_validate(data)
        except Exception as e:
            log.error("Planner JSON failed PlanResult validation: %s", e)
            raise typer.Exit(code=2) from e

        print(f"Plan OK, steps={len(plan_obj.steps)}")

    asyncio.run(_run())