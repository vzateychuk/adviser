from __future__ import annotations

from cfg.schema import AppConfig, ModelsRegistry
from flows.pec.critic import Critic
from flows.pec.ocr_executor import OcrExecutor
from flows.pec.orchestrator import Orchestrator
from flows.pec.planner import Planner
from flows.pec.schema_catalog import SchemaCatalog
from llm.client_factory import LLMClientFactory
from tools.prompt import load_role_prompts



def build_pec(
    *,
    llm_factory: LLMClientFactory,
    app_cfg: AppConfig,
    models_registry: ModelsRegistry,
) -> Orchestrator:
    """Wire the PEC flow together from config, prompts, models, and schemas.

    Centralizing composition keeps the runtime consistent across the full flow
    and the isolated CLI commands.
    """

    planner_model = models_registry.models["planner"].primary
    ocr_model = models_registry.models["ocr_executor"].primary
    critic_model = models_registry.models["critic"].primary

    planner_system_prompt, planner_user_template = load_role_prompts(
        "planner", prompts_dir=app_cfg.prompts_dir
    )
    ocr_system_prompt, ocr_user_template = load_role_prompts(
        "ocr_executor", prompts_dir=app_cfg.prompts_dir
    )
    critic_system_prompt, critic_user_template = load_role_prompts(
        "critic", prompts_dir=app_cfg.prompts_dir
    )

    schema_catalog = SchemaCatalog("flows/pec/schemas")

    planner = Planner(
        llm=llm_factory.for_model(planner_model),
        system_prompt=planner_system_prompt,
        user_template=planner_user_template,
        schema_catalog=schema_catalog,
    )
    executor = OcrExecutor(
        llm=llm_factory.for_model(ocr_model),
        system_prompt=ocr_system_prompt,
        user_template=ocr_user_template,
        schema_catalog=schema_catalog,
    )
    critic = Critic(
        llm=llm_factory.for_model(critic_model),
        system_prompt=critic_system_prompt,
        user_template=critic_user_template,
        schema_catalog=schema_catalog,
    )

    max_retries = app_cfg.orchestrator.max_retries if hasattr(app_cfg, "orchestrator") else 3
    return Orchestrator(
        planner=planner,
        executor=executor,
        critic=critic,
        max_retries=max_retries,
    )
