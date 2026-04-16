from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_plan_command_works_in_test_env():
    r = runner.invoke(app, ["--env", "test", "plan", "make a plan"])
    assert r.exit_code == 0
    assert "Plan OK, steps=" in r.stdout

def test_plan_command_in_test_env_returns_ok():
    r = runner.invoke(app, ["--env", "test", "plan", "Make a plan"])
    assert r.exit_code == 0
    assert "Plan OK, steps=" in r.stdout
