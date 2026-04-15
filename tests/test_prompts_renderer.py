from tools.prompts import render_template


def test_render_template_replaces_placeholders():
    template = "A={{A}} B={{B}}"
    values = {"A": "1", "B": "2"}
    out = render_template(template, values)
    assert out == "A=1 B=2"


def test_render_template_ignores_extra_values():
    template = "A={{A}}"
    values = {"A": "1", "EXTRA": "x"}
    out = render_template(template, values)
    assert out == "A=1"


def test_render_template_does_not_crash_on_missing_values():
    template = "A={{A}} B={{B}}"
    values = {"A": "1"}  # B is missing
    out = render_template(template, values)
    # B stays unresolved, but render must not crash
    assert out == "A=1 B={{B}}"