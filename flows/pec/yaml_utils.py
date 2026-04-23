from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import yaml

log = logging.getLogger(__name__)

_FENCED_YAML_RE = re.compile(r"```(?:yaml|yml)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def sanitize_llm_yaml(text: str) -> str:
    """Clean common LLM formatting artifacts before YAML parsing.

    We normalize fences, BOMs, and non-breaking spaces because models often emit
    them even when the prompt asks for raw YAML.
    
    Also fixes Windows paths with unescaped backslashes in double-quoted strings
    by converting them to single-quoted strings (which don't interpret escapes).
    """

    if not text:
        return ""

    cleaned = unicodedata.normalize("NFKC", text).strip()
    match = _FENCED_YAML_RE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()
    
    # Fix Windows paths in double-quoted strings: convert to single quotes
    # Pattern: "...\\..." -> '...\\...'
    # This prevents YAML from interpreting backslashes as escape sequences
    cleaned = re.sub(
        r'"([^"]*\\[^"]*?)"',
        lambda m: f"'{m.group(1)}'",
        cleaned
    )
    
    return cleaned



def load_llm_yaml(text: str) -> dict[str, Any]:
    """Parse YAML from an LLM response after removing common formatting noise.

    This keeps planner and critic tolerant to near-valid responses while still
    rejecting payloads that are not mapping-shaped YAML.
    """

    cleaned = sanitize_llm_yaml(text)

    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError as e:
        log.error("YAML parsing failed. Cleaned payload:\n%s", cleaned)
        raise ValueError(f"Invalid YAML format: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"LLM response must be a YAML mapping (dict), got {type(data).__name__}")

    return data
