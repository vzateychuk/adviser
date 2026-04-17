from pathlib import Path

from cfg.loader import load_app


def test_load_app_parses_prompts_dir(tmp_path: Path):
    """
    This test verifies that cfg.loader.load_app():
    - reads app.yaml from a given config directory
    - validates it via Pydantic (schema-level contract)
    - parses prompts_dir into a Path-like value that will be used to load prompts/*.md
    """
    cfg_dir = tmp_path / "prod"
    cfg_dir.mkdir()

    (cfg_dir / "app.yaml").write_text(
        """
version: "1.0"
llm:
  provider: "openai"
  base_url: "http://localhost:4000"
db:
  path: ".data/db/advisor.sqlite"
prompts_dir: "prompts"
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_app(cfg_dir)

    assert cfg.version == "1.0"
    assert cfg.llm.provider == "openai"
    assert str(cfg.prompts_dir) == "prompts"