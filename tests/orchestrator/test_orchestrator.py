from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cfg.loader import load_app, load_models
from cfg.schema import OrchestratorConfig
from llm.mock import MockLLMClient
from llm.mock_scenarios import executor_mock, planner_mock
from llm.types import ChatRequest, ChatResponse
from orchestrator.build_orchestrator import build_orchestrator
from orchestrator.models import RunStatus

_CFG_DIR = Path("config/test")


# ---------------------------------------------------------------------------
# Helpers — review scenarios
# ---------------------------------------------------------------------------

def _approve_always(req: ChatRequest) -> ChatResponse:
    payload = {"approved": True, "issues": [], "summary": "All criteria met"}
    return ChatResponse(text=json.dumps(payload))


def _reject_always(req: ChatRequest) -> ChatResponse:
    payload = {
        "approved": False,
        "issues": [
            {
                "severity": "high",
                "description": "Output is incomplete",
                "suggestion": "Add more detail to fully address the step",
            }
        ],
        "summary": "Step output does not meet success criteria",
    }
    return ChatResponse(text=json.dumps(payload))


def _reject_n_then_approve(n: int):
    """Reviewer scenario: rejects the first n calls, then approves."""
    state = {"calls": 0}

    def scenario(req: ChatRequest) -> ChatResponse:
        state["calls"] += 1
        if state["calls"] <= n:
            payload = {
                "approved": False,
                "issues": [
                    {
                        "severity": "medium",
                        "description": "Answer is too brief",
                        "suggestion": "Expand the response with concrete examples",
                    }
                ],
                "summary": f"Rejected on call {state['calls']}",
            }
        else:
            payload = {"approved": True, "issues": [], "summary": "Approved"}
        return ChatResponse(text=json.dumps(payload))

    return scenario


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _build(reviewer_scenario, max_retries: int = 3):
    """Build a test orchestrator with a custom review and max_retries override."""
    app_cfg = load_app(_CFG_DIR).model_copy(
        update={"orchestrator": OrchestratorConfig(max_retries=max_retries)}
    )
    models_registry = load_models(_CFG_DIR)
    llm = MockLLMClient(
        planner=planner_mock,
        executor=executor_mock,
        reviewer=reviewer_scenario,
    )
    return build_orchestrator(llm=llm, app_cfg=app_cfg, models_registry=models_registry)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_returns_result_when_approved_on_first_attempt():
    """Happy path: review approves immediately, no retries."""
    ctx = asyncio.run(_build(_approve_always).run("test request"))

    assert ctx.status == RunStatus.SUCCESS
    assert len(ctx.step_results) == 1
    assert ctx.retry_count == 0
    assert "Mock executor output" in ctx.step_results[0].content


def test_run_retries_on_reject_then_approves():
    """Reviewer rejects once, approves on second attempt."""
    ctx = asyncio.run(_build(_reject_n_then_approve(n=1), max_retries=3).run("test request"))

    assert ctx.status == RunStatus.SUCCESS
    assert len(ctx.step_results) == 1    # only the approved result stored in ctx
    assert ctx.retry_count == 1          # one rejection → one retry counted


def test_run_exhausts_max_retries_and_returns_fail():
    """Reviewer always rejects; orchestrator exits after max_retries without hanging."""
    ctx = asyncio.run(_build(_reject_always, max_retries=2).run("test request"))

    assert ctx.status == RunStatus.FAIL
    assert len(ctx.step_results) == 0    # no approved results
    assert ctx.retry_count == 2          # both attempts were rejections
