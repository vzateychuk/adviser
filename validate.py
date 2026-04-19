import asyncio

from orchestrator.build_orchestrator import build_orchestrator
from llm.factory import create_llm
from cfg.loader import load_app, load_models


async def main():
  from pathlib import Path

  BASE_DIR = Path(__file__).resolve().parents[0]

  config_dir = BASE_DIR / "config" / "dev"
  app_cfg = load_app(config_dir)
  models_registry = load_models(config_dir)
  llm = create_llm(env="dev", app_cfg=app_cfg)

  orchestrator = build_orchestrator(llm=llm, app_cfg=app_cfg, models_registry=models_registry)

  result = await orchestrator.run("Make a plan to write Python code that prints 'Hello, world!'. Plan in minimum 3 steps, and execute the plan.")

  print(result.status)
  print(result.step_results)


asyncio.run(main())