from __future__ import annotations

from llm.protocol import LLMClient
from cfg.schema import AppConfig, ModelsRegistry
from orchestrator.reviewer import Reviewer
from tools.prompt import load_role_prompts

from orchestrator.orchestrator import Orchestrator
from orchestrator.planner import Planner
from orchestrator.router import ExecutorRouter
from orchestrator.executors.generic import GenericExecutor
from orchestrator.executors.code import CodeExecutor


def build_orchestrator(
    *,
    llm: LLMClient,
    app_cfg: AppConfig,
    models_registry: ModelsRegistry,
) -> Orchestrator:
  """
  Composition root for Orchestrator v0.

  Resolves:
  - model aliases
  - prompts
  - executor wiring

  Returns fully constructed orchestrator with no external dependencies.
  """

  # Resolve models (roles → concrete model names)
  planner_model = models_registry.models["planner"].primary
  generic_model = models_registry.models["generic_executor"].primary
  code_model = models_registry.models["code_executor"].primary
  reviewer_model = models_registry.models["reviewer"].primary

  planner_system_prompt, planner_user_template = load_role_prompts("planner",
                                                                   prompts_dir=app_cfg.prompts_dir)
  generic_system_prompt, generic_user_template = load_role_prompts(
    "generic_executor",
    prompts_dir=app_cfg.prompts_dir,
  )
  code_system_prompt, code_user_template = load_role_prompts(
    "code_executor",
    prompts_dir=app_cfg.prompts_dir,
  )
  reviewer_system_prompt, reviewer_user_template = load_role_prompts("reviewer",
                                                                 prompts_dir=app_cfg.prompts_dir)

  # Planner
  planner = Planner(
    llm=llm,
    model=planner_model,
    system_prompt=planner_system_prompt,
    user_template=planner_user_template,
  )

  # Executors
  executors = {
    "generic": GenericExecutor(
      llm=llm,
      model_name=generic_model,
      system_prompt=generic_system_prompt,
      user_template=generic_user_template,
    ),
    "code": CodeExecutor(
      llm=llm,
      model_name=code_model,
      system_prompt=code_system_prompt,
      user_template=code_user_template,
    ),
  }

  # Reviewer
  reviewer = Reviewer(
    llm=llm,
    model=reviewer_model,
    system_prompt=reviewer_system_prompt,
    user_template=reviewer_user_template,
  )

  # Router
  router = ExecutorRouter()

  # Orchestrator
  return Orchestrator(
    planner=planner,
    executors=executors,
    router=router,
    reviewer=reviewer,
    max_retries=app_cfg.orchestrator.max_retries,
  )
