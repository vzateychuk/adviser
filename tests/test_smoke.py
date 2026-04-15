from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()

def test_default_env():
    r = runner.invoke(app, [])
    assert r.exit_code == 0

def test_cli_runs_in_test_env():
    # Integration smoke test: runs the CLI with --env=test and expects a clean exit.
    r = runner.invoke(app, ["--env", "test"])
    assert r.exit_code == 0
