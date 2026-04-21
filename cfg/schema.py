from __future__ import annotations

from pydantic import BaseModel
from typing import Literal
from pathlib import Path


AgentRole = Literal[
    # PEC flow
    "planner", "ocr_executor", "critic",
    # Medic Hub-and-Spoke (future)
    "coordinator", "ocr", "dialogue", "web_search", "synthesis", "knowledge_base",
]


class RoleModelChoice(BaseModel):
    """Model alias selection for a specific role (primary + optional fallback)."""

    primary: str
    fallback: str | None = None


class ModelsRegistry(BaseModel):
    """
    Environment-specific model registry.

    This file maps each internal role to a model alias (as configured in LiteLLM),
    without duplicating provider parameters (api_base/api_key/model_list).
    """

    version: str = "1.0"
    models: dict[AgentRole, RoleModelChoice]

LLMProvider = Literal["openai", "anthropic", "mock"]

class LLMConfig(BaseModel):
    """
    LLM runtime configuration for the current environment.

    provider:
      - openai: OpenAI-compatible API (e.g. LiteLLM proxy)
      - anthropic: Claude SDK/API (future)
      - mock: deterministic fake client for tests
    """
    provider: LLMProvider
    base_url: str | None = None

class DBConfig(BaseModel):
    """SQLite database configuration."""
    path: Path

class OrchestratorConfig(BaseModel):
    """PEC orchestrator runtime settings."""
    max_retries: int = 3


class AppConfig(BaseModel):
    """
    Application-level configuration (per environment).
    """

    version: str = "1.0"
    llm: LLMConfig
    db: DBConfig
    prompts_dir: Path = Path("prompts")
    orchestrator: OrchestratorConfig = OrchestratorConfig()
