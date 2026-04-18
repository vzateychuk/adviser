from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal, Mapping

log = logging.getLogger(__name__)

PromptType = Literal["system", "user"]
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def load_role_prompt(
    role_name: str,
    type: PromptType = "system",
    prompts_dir: Path | str | None = None,
) -> str:
    """Load a role prompt file from prompts/{role}/{type}.md."""
    prompts_root = Path(prompts_dir) if prompts_dir is not None else Path("prompts")
    path = prompts_root / role_name / f"{type}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_role_prompts(
    role_name: str,
    prompts_dir: Path | str | None = None,
) -> tuple[str, str]:
    """Load both system and user prompts for a role."""
    return (
        load_role_prompt(role_name, "system", prompts_dir=prompts_dir),
        load_role_prompt(role_name, "user", prompts_dir=prompts_dir),
    )


def render_template(template: str, values: Mapping[str, str]) -> str:
    """Render {{PLACEHOLDER}} values using a dictionary."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    rendered = _PLACEHOLDER_RE.sub(repl, template)
    missing = sorted(set(_PLACEHOLDER_RE.findall(rendered)))
    if missing:
        log.warning("Unresolved prompt placeholders: %s", missing)
    return rendered
