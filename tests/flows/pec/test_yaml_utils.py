from flows.pec.yaml_utils import load_llm_yaml


def test_load_llm_yaml_handles_fenced_yaml_and_nbsp():
    text = (
        "```yaml\n"
        "action: PLAN\n"
        "goal: Example\n"
        "schema_name: lab\n"
        "\u00a0 - schema exists\n"
        "steps: []\n"
        "```"
    )

    data = load_llm_yaml(text)

    assert data["action"] == "PLAN"
    assert data["schema_name"] == "lab"

