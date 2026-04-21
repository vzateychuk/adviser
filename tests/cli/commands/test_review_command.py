import json

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

_STEP = {
    "id": 1,
    "title": "Summarize findings",
    "type": "generic",
    "input": "Explain why unit tests matter",
    "output": "short explanation",
    "success_criteria": ["covers main reasons", "concise"],
}

_RESULT = {
    "id": 1,
    "executor": "generic",
    "content": "Unit tests catch regressions early and document intent.",
    "assumptions": [],
}


def test_review_approves_valid_step():
    r = runner.invoke(
        app,
        ["--env", "test", "review", json.dumps(_STEP), json.dumps(_RESULT)],
    )
    assert r.exit_code == 0


def test_review_invalid_step_json():
    r = runner.invoke(
        app,
        ["--env", "test", "review", "not-valid-json", json.dumps(_RESULT)],
    )
    assert r.exit_code != 0


def test_review_invalid_result_json():
    r = runner.invoke(
        app,
        ["--env", "test", "review", json.dumps(_STEP), "{broken"],
    )
    assert r.exit_code > 0
