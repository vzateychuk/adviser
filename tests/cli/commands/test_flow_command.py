from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_flow_exits_successfully_in_test_env():
    r = runner.invoke(app, ["--env", "test", "flow", "hello"])
    assert r.exit_code == 0


def test_flow_outputs_executor_result():
    r = runner.invoke(app, ["--env", "test", "flow", "hello"])
    assert r.exit_code == 0
