from __future__ import annotations

from typing import Protocol, TypeVar, overload

from pydantic import BaseModel

from common.types import ChatRequest, ChatResponse


T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """Vendor-agnostic LLM client protocol.

    All business logic (Planner, Executor, Critic) depends on this protocol,
    never on SDK-specific clients. This keeps the core domain portable across
    OpenAI, Anthropic, local models, and test mocks.

    Methods:
        chat: Legacy unstructured text completion (for backward compatibility)
        chat_structured: Typed completion using Pydantic model as response schema
    """

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Send a chat request and receive raw text response.

        Use this for free-form generation where no schema enforcement is needed.
        Prefer chat_structured() for all typed agent outputs.
        """
        ...

    async def chat_structured(
        self,
        req: ChatRequest,
        response_model: type[T],
        *,
        max_retries: int = 2,
    ) -> T:
        """Send a chat request and receive a validated Pydantic model.

        The adapter is responsible for:
        1. Injecting JSON schema into the prompt (via instructor or native API)
        2. Parsing and validating the response
        3. Retrying on validation failures (up to max_retries)

        Args:
            req: Chat request with system/user messages
            response_model: Pydantic model class defining expected response shape
            max_retries: Number of retry attempts on validation failure

        Returns:
            Validated instance of response_model

        Raises:
            StructuredOutputError: When validation fails after all retries
            LLMError: On transport/API errors
        """
        ...
