import logging
from pathlib import Path

import typer

from cfg.loader import load_app, load_models
from db.runtime import Database
from llm.factory import create_llm
from tools.logging import setup_logging
from cli.commands.ask import ask
from cli.commands.plan import plan
from cli.commands.flow import flow
from cli.commands.review import review
from cli.commands.exec import exec_step

app = typer.Typer(add_completion=False, invoke_without_command=True)


@app.callback()
def main(
    ctx: typer.Context,
    env: str = typer.Option("dev", "--env"),
    config_dir: Path | None = typer.Option(None, "--config-dir"),
) -> None:
    setup_logging(env)
    log = logging.getLogger("advisor")
    log.info("Starting app (env=%s)", env)

    cfg_dir = config_dir or (Path("config") / env)

    log.debug("Read configs from %s", cfg_dir)
    models_registry = load_models(cfg_dir)
    app_cfg = load_app(cfg_dir)

    llm_client = create_llm(env=env, app_cfg=app_cfg)

    ctx.obj = {
        "env": env,
        "models_registry": models_registry,
        "app_cfg": app_cfg,
        "prompts_dir": app_cfg.prompts_dir,
        "llm": llm_client,
    }

    log.info("Loaded models.yaml from %s (version=%s)", cfg_dir, models_registry.version)

    with Database(app_cfg.db.path) as db:
        db.record_run(env)
        log.info("Run stored in DB: %s", app_cfg.db.path)


# Register commands at module import time
app.command()(ask)  # Single ask step (no planning, no review)
app.command()(plan) # Only the planner, no execution, no review
app.command()(review) # Only the reviewer, for debugging or manual review of plan steps
app.command("exec-step")(exec_step) # Execute a single step with the executor, for debugging or manual review
app.command()(flow) # Full flow: plan + review + exec in a loop until done
