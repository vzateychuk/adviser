import logging
from pathlib import Path

import typer

from cfg.loader import load_models
from db.db import init_db
from tools.logging import setup_logging

app = typer.Typer(add_completion=False, invoke_without_command=True)


@app.callback()
def main(
    env: str = typer.Option("dev", "--env"),
    db_path: Path = typer.Option(Path(".data/db/advisor.sqlite"), "--db-path"),
    config_dir: Path | None = typer.Option(None, "--config-dir"),
) -> None:
    setup_logging(env)
    log = logging.getLogger("advisor")

    log.info("Starting app (env=%s)", env)

    cfg_dir = config_dir or (Path("config") / env)
    models_cfg = load_models(cfg_dir)
    log.info("Loaded models.yaml from %s (version=%s)", cfg_dir, models_cfg.version)
    log.info("planner.primary=%s", models_cfg.models["planner"].primary)

    conn = init_db(db_path)
    try:
        conn.execute("INSERT INTO runs(env) VALUES (?)", (env,))
        conn.commit()
        log.info("Run stored in DB: %s", db_path)
    finally:
        conn.close()