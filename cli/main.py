import logging
from pathlib import Path

import typer

from db.db import init_db
from tools.logging import setup_logging

app = typer.Typer(add_completion=False, invoke_without_command=True)


@app.callback()
def main(
    env: str = typer.Option("dev", "--env"),
    db_path: Path = typer.Option(Path(".data/db/advisor.sqlite"), "--db-path"),
) -> None:
    setup_logging(env)
    log = logging.getLogger("advisor")

    log.info("Starting app (env=%s)", env)

    conn = init_db(db_path)
    try:
        conn.execute("INSERT INTO runs(env) VALUES (?)", (env,))
        conn.commit()
        log.info("Run stored in DB: %s", db_path)
    finally:
        conn.close()