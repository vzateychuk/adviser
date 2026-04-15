from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from cfg.schema import ModelsConfig


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=16)
def load_models(config_dir: Path) -> ModelsConfig:
    data = _read_yaml(config_dir / "models.yaml")
    return ModelsConfig.model_validate(data)