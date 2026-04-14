from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()

def test_default_env():
    r = runner.invoke(app, [])
    assert r.exit_code == 0
    assert "env=dev" in r.stdout

def test_prod_env():
    r = runner.invoke(app, ["--env", "prod"])
    assert r.exit_code == 0
    assert "env=prod" in r.stdout