from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()
TEST_TMP = Path('.tmp-tests')
TEST_TMP.mkdir(exist_ok=True)



def test_plan_command_works_in_test_env():
    r = runner.invoke(app, ["--env", "test", "plan", "hemoglobin 120 g/L on 2024-01-01"])
    assert r.exit_code == 0
    assert "active_schema: lab" in r.stdout
    assert "status: planned" in r.stdout



def test_plan_command_reads_existing_file():
    path = TEST_TMP / "doc.txt"
    path.write_text("consultation note for patient", encoding="utf-8")
    r = runner.invoke(app, ["--env", "test", "plan", str(path)])
    assert r.exit_code == 0
    assert f"user_request: {path}" in r.stdout
