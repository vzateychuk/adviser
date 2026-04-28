from __future__ import annotations

import logging
import sys


def setup_logging(env: str) -> None:
    """
    Minimal logging setup for CLI app.
    dev  -> DEBUG
    prod -> INFO
    
    Logs go to stderr, output goes to stdout.
    """
    level = logging.DEBUG if env == "dev" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
        force=True,
    )
    logging.getLogger().handlers[0].stream = sys.stderr