from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


AgentRole = Literal["planner", "generic_executor", "code_executor", "critic"]


class RoleModelChoice(BaseModel):
    primary: str
    fallback: str | None = None

class ModelsConfig(BaseModel):
    """
    Environment-specific model routing configuration.

    This config does NOT define LiteLLM provider params. It only maps each agent role(planner/executors/critic) to a model alias that must exist in the LiteLLM proxy config.

    Example:
        models:
          planner:
            primary: "mistral-small-4-119b-2603"
            fallback: "llama-3.1-8b-instruct"
    """
    version: str = "1.0"
    models: dict[AgentRole, RoleModelChoice]
