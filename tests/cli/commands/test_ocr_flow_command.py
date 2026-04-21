from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_ocr_flow_in_test_env():
    """Full PEC pipeline runs without error in test (mock) environment."""
    r = runner.invoke(app, ["--env", "test", "ocr-flow", "scan.pdf"])
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")


def test_ocr_flow_with_context_in_test_env():
    """ocr-flow accepts an optional --context flag."""
    r = runner.invoke(
        app,
        ["--env", "test", "ocr-flow", "blood_test.pdf", "--context", "blood test scan"],
    )
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")
