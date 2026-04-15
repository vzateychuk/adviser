from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from db.db import init_db


@dataclass
class Database:
    """Runtime wrapper around SQLite connection for app bootstrap tasks."""
    path: Path
    _conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = init_db(self.path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def record_run(self, env: str) -> None:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        self._conn.execute("INSERT INTO runs(env) VALUES (?)", (env,))
        self._conn.commit()

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()