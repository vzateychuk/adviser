from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()
TEST_TMP = Path('.tmp-tests')
TEST_TMP.mkdir(exist_ok=True)



def test_ocr_flow_in_test_env():
    r = runner.invoke(app, ["--env", "test", "ocr-flow", "hemoglobin 120 g/L 2024-01-01"])
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")
    assert "laboratory_panel:" in r.stdout



def test_ocr_flow_with_context_in_test_env():
    r = runner.invoke(
        app,
        ["--env", "test", "ocr-flow", "blood_test.pdf", "--context", "blood test scan hemoglobin 120 g/L"],
    )
    assert r.exit_code == 0, r.stdout + "\n" + (r.stderr or "")
    assert "document:" in r.stdout



def test_exec_and_review_commands_roundtrip():
    ctx = TEST_TMP / "context.yaml"
    ctx.write_text(
        """
user_request: hemoglobin 120 g/L

document_content: hemoglobin 120 g/L 2024-01-01
plan:
  action: PLAN
  goal: Extract lab data
  schema_name: lab
  assumptions: []
  steps:
    - id: 1
      title: Extract lab values
      type: ocr
      input: hemoglobin 120 g/L
      output: lab
      success_criteria:
        - all numeric values match the source
        - all dates match the source
        - all units match the source when present
active_schema: lab
steps_results: []
critic_feedback: []
status: planned
""".strip(),
        encoding="utf-8",
    )

    exec_res = runner.invoke(app, ["--env", "test", "exec", str(ctx)])
    assert exec_res.exit_code == 0, exec_res.stdout + "\n" + (exec_res.stderr or "")
    assert "status: completed" in exec_res.stdout
    assert "laboratory_panel:" in exec_res.stdout

    reviewed_ctx = TEST_TMP / "review.yaml"
    reviewed_ctx.write_text(exec_res.stdout, encoding="utf-8")
    review_res = runner.invoke(app, ["--env", "test", "review", str(reviewed_ctx)])
    assert review_res.exit_code == 0, review_res.stdout + "\n" + (review_res.stderr or "")
    assert "critic_feedback: []" in review_res.stdout
