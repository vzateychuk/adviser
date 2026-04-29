from flows.pec.models import PlanAction, PlanResult, PlanStep, RunContext
from flows.pec.renderer import render_planner_prompt, render_step_template


def test_render_step_template_replaces_placeholders():
    step = PlanStep(
        id=1,
        title="Title",
        type="ocr",
        input="Input",
        output="Output",
        success_criteria=["one", "two"],
    )
    context = RunContext(
        user_request="request",
        document_content="document text",
        plan=PlanResult(goal="goal", action=PlanAction.PLAN, schema_name="lab", steps=[step]),
        active_schema="lab",
    )
    template = "T={{STEP_TITLE}} I={{STEP_INPUT}} O={{STEP_OUTPUT}} S={{STEP_SUCCESS_CRITERIA}} P=prev A={{ACTIVE_SCHEMA}}"
    out = render_step_template(context, step, template, previous_results="prev", critic_feedback="feedback")
    assert "T=Title I=Input O=Output" in out
    assert "S=one" in out
    assert "two" in out
    assert "P=prev A=lab" in out