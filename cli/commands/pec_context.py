from __future__ import annotations

from pathlib import Path

from flows.pec.models import RunContext



def resolve_document_input(value: str) -> tuple[str, str]:
    """Resolve a CLI argument as either a file path or inline document text.

    This keeps the debug commands ergonomic: users can point at a real file or
    paste text directly without changing the command surface.
    """

    path = Path(value)
    if path.exists():
        return str(path), path.read_text(encoding="utf-8")
    return value, value



def build_initial_context(value: str) -> RunContext:
    """Create the initial RunContext from CLI input before planning starts.

    We derive both user request and document content here so the rest of the flow
    can operate on a single normalized state object.
    """

    user_request, document_content = resolve_document_input(value)
    return RunContext(user_request=user_request, document_content=document_content)
