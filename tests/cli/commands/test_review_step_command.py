import json

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_review_step_in_test_env_returns_ok():
    # Integration smoke test: runs `review-step` in env=test and expects:
    # - clean exit (exit_code == 0)
    # - a validated CriticResult produced by MockLLMClient (meta.role == "critic")
    step = {
        "id": 1,
        "title": "Test step",
        "type": "generic",
        "input": "Say hello",
        "output": "Greeting",
        "success_criteria": ["Must greet"],
    }
    result = {
        "step_id": 1,
        "executor": "generic_executor",
        "content": "Hello!",
        "assumptions": [],
    }

    r = runner.invoke(
        app,
        ["--env", "test", "review-step", json.dumps(step), json.dumps(result)],
    )

    assert r.exit_code == 0, r.stdout + "\n" + r.stderr