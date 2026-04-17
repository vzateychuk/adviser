import json
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_exec_step_generic_in_test_env():
    step = {
        "id": 1,
        "title": "Test generic",
        "type": "generic",
        "input": "Say hello",
        "output": "Greeting",
        "success_criteria": ["Must greet"],
    }
    r = runner.invoke(app, ["--env", "test", "exec-step", json.dumps(step)])
    assert r.exit_code == 0
    assert "[MOCK]" in r.output