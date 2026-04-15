from __future__ import annotations

import logging


def setup_logging(env: str) -> None:
    """
    Minimal logging setup for CLI app.
    dev  -> DEBUG
    prod -> INFO
    """
    level = logging.DEBUG if env == "dev" else logging.INFO
    logging.basicConfig(
        level=level,
            format=("%(asctime)s | %(levelname)s | %(name)s | ""%(filename)s:%(lineno)d | %(message)s"
        ),
    )