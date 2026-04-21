"""
Error-path tests for all CLI commands.

Covers:
- invalid JSON input to exec-step and review
- unknown step type in exec-step
- LLM failure (exit code 2) for every command
"""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from cli.main import app
from llm.errors import LLMError
from llm.mock import MockLLMClient

runner = CliRunner()

_STEP = {
    "id": 1,
    "title": "test step",
    "type": "generic",
    "input": "say hello",
    "output": "greeting",
    "success_criteria": ["must greet"],
}

_RESULT = {
    "id": 1,
    "executor": "generic",
    "content": "Hello!",
    "assumptions": [],
}


# ---------------------------------------------------------------------------
# Invalid-input error paths (no LLM call needed)
# ---------------------------------------------------------------------------

def test_exec_step_invalid_json():
    r = runner.invoke(app, ["--env", "test", "exec-step", "not-json"])
    assert r.exit_code == 2


def test_exec_step_unknown_step_type():
    bad_step = {**_STEP, "type": "unknown_type"}
    r = runner.invoke(app, ["--env", "test", "exec-step", json.dumps(bad_step)])
    assert r.exit_code == 2


def test_review_invalid_step_json_returns_error():
    r = runner.invoke(
        app, ["--env", "test", "review", "not-json", json.dumps(_RESULT)]
    )
    assert r.exit_code != 0


def test_review_invalid_result_json_returns_error():
    r = runner.invoke(
        app, ["--env", "test", "review", json.dumps(_STEP), "{broken"]
    )
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# LLM-failure error paths
# ---------------------------------------------------------------------------

def _failing_llm() -> MockLLMClient:
    """MockLLMClient whose every scenario raises LLMError."""

    def _fail(req):
        raise LLMError("Simulated LLM failure")

    return MockLLMClient(planner=_fail, executor=_fail, reviewer=_fail, default=_fail)


def test_ask_exits_with_error_on_llm_failure(monkeypatch):
    monkeypatch.setattr("cli.main.create_llm", lambda **kw: _failing_llm())
    r = runner.invoke(app, ["--env", "test", "ask", "hello"])
    assert r.exit_code == 2


def test_plan_exits_with_error_on_llm_failure(monkeypatch):
    monkeypatch.setattr("cli.main.create_llm", lambda **kw: _failing_llm())
    r = runner.invoke(app, ["--env", "test", "plan", "make a plan"])
    assert r.exit_code == 2


def test_exec_step_exits_with_error_on_llm_failure(monkeypatch):
    monkeypatch.setattr("cli.main.create_llm", lambda **kw: _failing_llm())
    r = runner.invoke(
        app, ["--env", "test", "exec-step", json.dumps(_STEP)]
    )
    assert r.exit_code == 2


def test_flow_exits_with_error_on_llm_failure(monkeypatch):
    monkeypatch.setattr("cli.main.create_llm", lambda **kw: _failing_llm())
    r = runner.invoke(app, ["--env", "test", "flow", "hello"])
    assert r.exit_code == 2


def test_review_exits_with_error_on_llm_failure(monkeypatch):
    monkeypatch.setattr("cli.main.create_llm", lambda **kw: _failing_llm())
    r = runner.invoke(
        app,
        ["--env", "test", "review", json.dumps(_STEP), json.dumps(_RESULT)],
    )
    assert r.exit_code == 2
