from flows.pec.models import StepResult
from flows.pec.renderer import summarize_previous_results



def test_summarize_previous_results_limits_lines():
    content = "\n".join([f"line{i}" for i in range(50)])
    prev = [StepResult(step_id=1, executor="ocr", doc=None)]
    out = summarize_previous_results(None, max_lines=20)

    assert "line0" in out
    assert "line19" in out
    assert "line20" not in out
