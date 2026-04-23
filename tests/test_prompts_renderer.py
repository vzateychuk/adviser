from flows.pec.models import PlanAction, PlanResult, PlanStep, RunContext
from flows.pec.renderer import render_planner_prompt, render_step_template
from flows.pec.schema_catalog import SchemaCatalog



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
    schema = SchemaCatalog("flows/pec/schemas").get("lab")
    template = "T={{STEP_TITLE}} I={{STEP_INPUT}} O={{STEP_OUTPUT}} S={{STEP_SUCCESS_CRITERIA}} P={{PREVIOUS_RESULTS}} A={{ACTIVE_SCHEMA}}"
    out = render_step_template(context, step, template, previous_results="prev", schema=schema)
    assert out == "T=Title I=Input O=Output S=one\ntwo P=prev A=lab"



def test_render_step_template_includes_critic_feedback():
    step = PlanStep(
        id=1,
        title="Title",
        type="ocr",
        input="Input",
        output="Output",
        success_criteria=["one"],
    )
    context = RunContext(
        user_request="request",
        document_content="document text",
        plan=PlanResult(goal="goal", action=PlanAction.PLAN, schema_name="lab", steps=[step]),
        active_schema="lab",
    )
    template = "T={{STEP_TITLE}} F={{CRITIC_FEEDBACK}}"
    out = render_step_template(context, step, template, critic_feedback="retry reason")
    assert out == "T=Title F=retry reason"



def test_render_planner_prompt_includes_schema_catalog():
    out = render_planner_prompt(
        user_request="scan.pdf",
        document_content="hemoglobin 120 g/L",
        schema_catalog_summary="- id: lab",
        template="R={{USER_REQUEST}} D={{DOCUMENT_CONTENT}} C={{SCHEMA_CATALOG}}",
    )
    assert "R=scan.pdf" in out
    assert "hemoglobin 120 g/L" in out
    assert "- id: lab" in out
