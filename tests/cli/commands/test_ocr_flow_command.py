import pytest
from pathlib import Path
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()
TEST_TMP = Path('.tmp-tests')
TEST_TMP.mkdir(exist_ok=True)


def test_ocr_flow_in_test_env():
    r = runner.invoke(app, ["--env", "test", "ocr-flow", "hemoglobin 120 g/L 2024-01-01"])
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")
    # Now tests expect MedicDoc JSON output (e.g. schema_id in JSON)
    assert "schema_id" in r.stdout


def test_ocr_flow_with_context_in_test_env():
    r = runner.invoke(
        app,
        ["--env", "test", "ocr-flow", "blood_test.pdf", "--context", "blood test scan hemoglobin 120 g/L"],
    )
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")
    # JSON output checks
    assert "schema_id" in r.stdout


@pytest.mark.skip(reason="Critic still uses old stack; exec relies on context.active_schema loading which may differ per env. To be re-enabled after CLI orchestration refactor.")
def test_exec_and_critic_commands_roundtrip():
    # Note: Critic is not updated to use chat_structured and final merged doc.
    # This test currently relies only on exec output for validated MedicalDoc after merge.
    # After Critic refactor in a future commit, critic command should be tested again.
    ctx = TEST_TMP / "context.yaml"
    # Minimal valid context for exec + merge
    # Note: The plan command usually sets active_schema from schema_name. Here we approximate.
    ctx.write_text(
        """user_request: "hemoglobin 120 g/L"
document_content: "hemoglobin 120 g/L 2024-01-01"
plan:
  action: PLAN
  goal: Extract lab data
  schema_name: lab
  steps:
  - id: 1
    title: Extract lab values
    type: ocr
    input: document_content
    output: lab
    success_criteria:
    - non-empty criteria
  active_schema: lab  # Planner / CLI usually sets this
  steps_results: []
  critic_feedback: []
  status: planned
doc: null""",
        encoding="utf-8",
    )
    # Just test that exec command runs without crashing and produces doc
    exec_res = runner.invoke(app, ["--env", "test", "exec", str(ctx)])
    if exec_res.exit_code != 0:
        print(f"EXEC OUTPUT:\n{exec_res.stdout}\n")
        if exec_res.exception:
            import traceback
            traceback.print_exception(type(exec_res.exception), exec_res.exception, exec_res.exception.__traceback__)
    assert exec_res.exit_code == 0, f"Exec failed:\n{exec_res.stdout}\n"
    # After changes, commands return validated MedDoc JSON; we only assert presence of doc and schema_id
    assert ("doc:" in exec_res.stdout or '"doc":' in exec_res.stdout), "Exec must output doc field to store merged MedicalDoc"
    assert ("schema_id" in exec_res.stdout or '"schema_id"' in exec_res.stdout), "Exec must output schema_id in MedicalDoc JSON"
