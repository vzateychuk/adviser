from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from common.types import AppConfig, ModelsRegistry


def _read_yaml(path: Path) -> dict:
    """Reads a YAML file and returns a dict (empty dict if file is empty)."""
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=16)
def load_models(config_dir: Path) -> ModelsRegistry:
    """
    Loads and validates models.yaml for the given environment config directory.

    Example directory: config/prod
    """
    data = _read_yaml(config_dir / "models.yaml")
    return ModelsRegistry.model_validate(data)


@lru_cache(maxsize=16)
def load_app(config_dir: Path) -> AppConfig:
    """
    Loads and validates app.yaml for the given environment config directory.

    app.yaml contains runtime settings like LLM base_url.
    """
    data = _read_yaml(config_dir / "app.yaml")
    return AppConfig.model_validate(data)