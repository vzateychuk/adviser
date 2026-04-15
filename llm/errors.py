from __future__ import annotations


class LLMError(Exception):
    """
    Base class for LLM client errors.

    All vendor-specific exceptions (e.g. openai.APIStatusError) are converted
    to this type at the adapter boundary so the rest of the application
    stays vendor-agnostic.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
