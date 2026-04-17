from pathlib import Path
from tools.prompts import load_role_prompt

def test_load_role_prompt_reads_file(tmp_path: Path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "planner.md").write_text("hello", encoding="utf-8")

    assert load_role_prompt("planner", prompts_dir=prompts_dir) == "hello"