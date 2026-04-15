from pathlib import Path

from db.runtime import Database


def test_database_records_run(tmp_path: Path):
    db_path = tmp_path / "test.sqlite"

    with Database(db_path) as db:
        db.record_run("test")

    # verify row was written
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("select env from runs order by id desc limit 1").fetchone()
        assert row is not None
        assert row[0] == "test"
    finally:
        conn.close()