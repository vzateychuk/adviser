from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Mapping

log = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_role_prompt(role: str, prompts_dir: Path = _DEFAULT_PROMPTS_DIR) -> str:
    """Load prompt template by convention: prompts/<role>.md"""
    path = prompts_dir / f"{role}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_template(template: str, values: Mapping[str, str]) -> str:
    """
    Render {{PLACEHOLDER}} values using a dictionary.

    Unresolved placeholders are kept as-is and logged as a warning.
    """
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    rendered = _PLACEHOLDER_RE.sub(repl, template)

    missing = sorted(set(_PLACEHOLDER_RE.findall(rendered)))
    if missing:
        log.warning("Unresolved prompt placeholders: %s", missing)

    return rendered