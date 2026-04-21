import asyncio
from pathlib import Path

from flows.pec.build_pec import build_pec
from llm.factory import create_llm
from cfg.loader import load_app, load_models


async def main():
    BASE_DIR = Path(__file__).resolve().parents[0]

    config_dir = BASE_DIR / "config" / "dev"
    app_cfg = load_app(config_dir)
    models_registry = load_models(config_dir)
    llm = create_llm(env="dev", app_cfg=app_cfg)

    orchestrator = build_pec(llm=llm, app_cfg=app_cfg, models_registry=models_registry)

    result = await orchestrator.run("sample_document.pdf", doc_context="medical scan")

    print(f"Schema: {result.schema_name}")
    print(f"Retries: {result.retry_count}")
    print(result.yaml_content)


asyncio.run(main())