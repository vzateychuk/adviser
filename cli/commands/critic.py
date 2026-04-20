from __future__ import annotations

import asyncio
import json
import logging
import re

import typer

from orchestrator.models import CriticResult, PlanStep, StepResult
from llm.errors import LLMError
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from tools.prompt import load_role_prompts, render_template

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


def critic(ctx: typer.Context, step_json: str, result_json: str) -> None:
    """
    Calls the Critic role to review a single review step.

    What it does:
    - Parses step_json into PlanStep
    - Parses result_json into StepResult
    - Calls the LLM using prompts/critic.md and expects JSON-only verdict
    - Validates response against CriticResult
    - Prints a compact verdict summary
    """
    if not ctx.obj:
        raise RuntimeError("CLI context is not initialized (ctx.obj is empty).")

    llm: LLMClient = ctx.obj["llm"]
    models_registry = ctx.obj["models_registry"]
    prompts_dir = ctx.obj["prompts_dir"]

    # Parse and validate inputs
    try:
        step = PlanStep.model_validate(json.loads(step_json))
    except Exception as e:
        raise typer.BadParameter(f"Invalid step_json (PlanStep): {e}") from e

    try:
        result = StepResult.model_validate(json.loads(result_json))
    except Exception as e:
        raise typer.BadParameter(f"Invalid result_json (StepResult): {e}") from e

    model_alias = models_registry.models["critic"].primary

    # Build critic prompt input (best-effort structured text)
    criteria_text = "\n".join(f"- {c}" for c in step.success_criteria)
    step_text = (
        f"title: {step.title}\n"
        f"type: {step.type}\n"
        f"input: {step.input}\n"
        f"expected_output: {step.output}\n"
    )

    system_prompt, user_template = load_role_prompts("critic", prompts_dir=prompts_dir)
    user_content = render_template(
        user_template,
        {
            "STEP": step_text,
            "STEP_RESULT": result.content,
            "SUCCESS_CRITERIA": criteria_text,
        },
    )

    async def _run() -> None:
        try:
            resp = await llm.chat(
                ChatRequest(
                    model=model_alias,
                    messages=[
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=user_content),
                    ],
                    # meta={"role": "critic"},
                )
            )
        except LLMError as e:
            log.error("Critic request failed. Model='%s'. Details: %s", model_alias, e)
            raise typer.Exit(code=2) from e

        json_text = _extract_json(resp.text)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            log.error("Critic returned non-JSON output. First 200 chars: %r", resp.text[:200])
            raise typer.Exit(code=2) from e

        try:
            verdict = CriticResult.model_validate(data)
        except Exception as e:
            log.error("Critic JSON failed CriticResult validation: %s", e)
            raise typer.Exit(code=2) from e

        print(f"Critic OK, approved={verdict.approved} issues={len(verdict.issues)}")

    asyncio.run(_run())
    raise typer.Exit(code=0)