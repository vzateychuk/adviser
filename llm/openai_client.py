from __future__ import annotations

import logging
from typing import Any, TypeVar, cast

import instructor
from openai import AsyncOpenAI, APIStatusError
from pydantic import BaseModel, ValidationError

from llm.errors import LLMError, StructuredOutputError
from llm.protocol import LLMClient
from common.types import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleClient(LLMClient):
    """Adapter for OpenAI-compatible Chat Completions API with instructor support.

    This client wraps the OpenAI SDK and integrates instructor for structured
    outputs. All vendor-specific details (SDK imports, error handling, JSON mode)
    are contained here — the rest of the application uses the LLMClient protocol.

    Structured outputs use instructor's patching mechanism which:
    1. Injects the Pydantic schema as a JSON schema in the API call
    2. Parses and validates the response automatically
    3. Retries on validation failure with error feedback to the model

    Notes:
    - We keep the rest of the application vendor-agnostic via the LLMClient protocol.
    - openai SDK typing is stricter than our internal message dicts, so we use `cast`
      at the adapter boundary to satisfy static type checkers (Pylance/mypy).
    - Vendor-specific exceptions (APIStatusError) are converted to LLMError here
      so callers outside llm/ never import openai directly.
    """

    def __init__(self, base_url: str, model_alias: str, timeout: float = 120.0) -> None:
        # openai SDK requires an api_key value, even if the proxy handles auth.
        self._raw_client = AsyncOpenAI(base_url=base_url, api_key="dummy", timeout=timeout)
        self._model_alias = model_alias

        # Instructor-patched client for structured outputs
        # Mode.JSON ensures we get parseable JSON even from non-OpenAI providers
        self._instructor_client = instructor.from_openai(
            self._raw_client,
            mode=instructor.Mode.JSON,
        )

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Legacy unstructured text completion.

        Use chat_structured() for typed outputs. This method is kept for
        backward compatibility and free-form generation tasks.
        """
        messages = cast(list[dict[str, Any]], [m.model_dump() for m in req.messages])
        log.debug("OpenAICompatibleClient.chat(model=%s, messages=%d)", self._model_alias, len(messages))

        try:
            resp = await self._raw_client.chat.completions.create(
                model=self._model_alias,
                messages=messages,
                stream=False,
            )
        except APIStatusError as e:
            raise LLMError(str(e), status_code=e.status_code) from e

        text = (resp.choices[0].message.content or "").strip()
        return ChatResponse(text=text, model_alias=self._model_alias)

    async def chat_structured(
        self,
        req: ChatRequest,
        response_model: type[T],
        *,
        max_retries: int = 2,
    ) -> T:
        """Send a chat request and receive a validated Pydantic model.

        Uses instructor to:
        1. Inject JSON schema derived from response_model into the prompt
        2. Parse the LLM response as JSON
        3. Validate against the Pydantic model
        4. Retry with validation feedback on failure

        Args:
            req: Chat request with system/user messages
            response_model: Pydantic model class (e.g., PlanResult)
            max_retries: Retry attempts on validation failure (instructor handles this)

        Returns:
            Validated instance of response_model

        Raises:
            StructuredOutputError: Validation failed after all retries
            LLMError: Transport/API error
        """
        messages = cast(list[dict[str, Any]], [m.model_dump() for m in req.messages])
        log.debug(
            "OpenAICompatibleClient.chat_structured(model=%s, response_model=%s, retries=%d)",
            self._model_alias,
            response_model.__name__,
            max_retries,
        )

        try:
            result = await self._instructor_client.chat.completions.create(
                model=self._model_alias,
                messages=messages,
                response_model=response_model,
                max_retries=max_retries,
                temperature=req.temperature,
            )
            log.debug("Structured output received: %s", type(result).__name__)
            return result

        except ValidationError as e:
            # Instructor exhausted retries but still failed validation
            log.warning(
                "Structured output validation failed after %d retries: %s",
                max_retries,
                e.error_count(),
            )
            raise StructuredOutputError(
                f"Failed to parse {response_model.__name__} after {max_retries} retries",
                validation_errors=e.errors(),
                attempts=max_retries + 1,
            ) from e

        except APIStatusError as e:
            raise LLMError(str(e), status_code=e.status_code) from e

        except Exception as e:
            # Catch-all for unexpected instructor errors
            log.exception("Unexpected error in chat_structured: %s", e)
            raise LLMError(f"Unexpected error: {e}") from e
