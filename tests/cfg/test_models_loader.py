from pathlib import Path

from cfg.loader import load_models


def test_load_models_test_env():
    # Ensures that config/test/models.yaml is loadable/valid
    # and that it maps roles to the "mock" model alias (used in test environment).
    cfg_dir = Path("config") / "test"
    cfg = load_models(cfg_dir)

    assert cfg.version == "1.0"
    assert cfg.models["planner"].primary == "mock"