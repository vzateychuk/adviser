from __future__ import annotations

from llm.protocol import LLMClient
from cfg.schema import AppConfig, ModelsRegistry
from tools.prompt import load_role_prompts

from flows.pec.orchestrator import PecOrchestrator
from flows.pec.planner import Planner
from flows.pec.critic import Critic
from flows.pec.executors.ocr import OcrExecutor


def build_pec(
    *,
    llm: LLMClient,
    app_cfg: AppConfig,
    models_registry: ModelsRegistry,
) -> PecOrchestrator:
    """
    Composition root for the OCR PEC flow.

    Resolves model aliases, loads prompts, wires Planner + OcrExecutor + Critic.
    Returns a fully constructed PecOrchestrator with no external dependencies.
    """

    # -------------------------
    # Resolve model aliases
    # -------------------------
    planner_model = models_registry.models["planner"].primary
    ocr_model = models_registry.models["ocr_executor"].primary
    critic_model = models_registry.models["critic"].primary

    # -------------------------
    # Load prompts
    # -------------------------
    planner_system_prompt, planner_user_template = load_role_prompts(
        "planner", prompts_dir=app_cfg.prompts_dir
    )
    ocr_system_prompt, ocr_user_template = load_role_prompts(
        "ocr_executor", prompts_dir=app_cfg.prompts_dir
    )
    critic_system_prompt, critic_user_template = load_role_prompts(
        "critic", prompts_dir=app_cfg.prompts_dir
    )

    # -------------------------
    # Planner
    # -------------------------
    planner = Planner(
        llm=llm,
        model=planner_model,
        prompt=planner_system_prompt,
    )

    # -------------------------
    # OcrExecutor
    # -------------------------
    executor = OcrExecutor(
        llm=llm,
        model_name=ocr_model,
        system_prompt=ocr_system_prompt,
        user_template=ocr_user_template,
    )

    # -------------------------
    # Critic
    # -------------------------
    critic = Critic(
        llm=llm,
        model=critic_model,
        system_prompt=critic_system_prompt,
        user_template=critic_user_template,
    )

    # -------------------------
    # Orchestrator
    # -------------------------
    max_retries = app_cfg.orchestrator.max_retries if hasattr(app_cfg, "orchestrator") else 3
    return PecOrchestrator(
        planner=planner,
        executor=executor,
        critic=critic,
        max_retries=max_retries,
    )
