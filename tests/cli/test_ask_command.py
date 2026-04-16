from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_ask_command_in_test_env_uses_mock():
    r = runner.invoke(app, ["--env", "test", "ask", "hello"])
    assert r.exit_code == 0
    assert "[MOCK]" in r.stdout