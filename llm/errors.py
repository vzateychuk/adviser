from __future__ import annotations

from typing import Any


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


class StructuredOutputError(LLMError):
    """Raised when structured output validation fails after all retries.

    This error contains the last raw response and validation errors for debugging.
    The Orchestrator can catch this to decide whether to retry with different
    prompts or fail the step.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_response: str | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.validation_errors = validation_errors or []
        self.attempts = attempts

    def __str__(self) -> str:
        base = super().__str__()
        if self.validation_errors:
            errors_str = "; ".join(
                f"{e.get('loc', '?')}: {e.get('msg', '?')}" 
                for e in self.validation_errors[:3]
            )
            return f"{base} (validation: {errors_str})"
        return base
