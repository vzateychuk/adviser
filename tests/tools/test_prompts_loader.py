from pathlib import Path

from tools.prompt import load_role_prompt, load_role_prompts


def test_load_role_prompt_reads_split_file(tmp_path: Path):
    prompts_dir = tmp_path / "prompts" / "planner"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("hello", encoding="utf-8")

    assert load_role_prompt("planner", "system", prompts_dir=tmp_path / "prompts") == "hello"


def test_load_role_prompts_reads_both_files(tmp_path: Path):
    prompts_dir = tmp_path / "prompts" / "planner"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("sys", encoding="utf-8")
    (prompts_dir / "user.md").write_text("user", encoding="utf-8")

    assert load_role_prompts("planner", prompts_dir=tmp_path / "prompts") == ("sys", "user")
