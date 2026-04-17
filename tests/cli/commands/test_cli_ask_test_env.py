from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_cli_ask_uses_mock_in_test_env():
    r = runner.invoke(app, ["--env", "test", "ask", "hello"])
    assert r.exit_code == 0