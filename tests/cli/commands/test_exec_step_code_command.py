import json
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_exec_step_code_in_test_env():
    step = {
        "id": 2,
        "title": "Test code",
        "type": "code",
        "input": "Write Python function add(a,b)->int",
        "output": "Code",
        "success_criteria": ["Valid Python"],
    }

    r = runner.invoke(app, ["--env", "test", "exec-step", json.dumps(step)])

    assert r.exit_code == 0, r.stdout + "\n" + r.stderr
    assert r.exit_code == 0