from flows.pec.prompting.renderer import summarize_previous_results
from flows.pec.models import StepResult


def test_summarize_previous_results_limits_lines():
    content = "\n".join([f"line{i}" for i in range(50)])
    prev = [StepResult(step_id=1, executor="ocr", content=content, assumptions=[])]
    out = summarize_previous_results(prev, max_lines=20)

    assert "line0" in out
    assert "line19" in out
    assert "line20" not in out