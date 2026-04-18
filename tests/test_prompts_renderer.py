from orchestrator.models import PlanStep
from orchestrator.prompting.renderer import render_step_template


def test_render_step_template_replaces_placeholders():
    step = PlanStep(
        id=1,
        title="Title",
        type="generic",
        input="Input",
        output="Output",
        success_criteria=["one", "two"],
    )
    template = "T={{STEP_TITLE}} I={{STEP_INPUT}} O={{STEP_OUTPUT}} S={{STEP_SUCCESS_CRITERIA}} P={{PREVIOUS_RESULTS}}"
    out = render_step_template(step, template, previous_results="prev")
    assert out == "T=Title I=Input O=Output S=one\ntwo P=prev"


def test_render_step_template_keeps_unknown_placeholders():
    step = PlanStep(
        id=1,
        title="Title",
        type="generic",
        input="Input",
        output="Output",
        success_criteria=["one"],
    )
    template = "A={{A}} T={{STEP_TITLE}}"
    out = render_step_template(step, template)
    assert out == "A={{A}} T=Title"
