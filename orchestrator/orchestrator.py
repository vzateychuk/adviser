from __future__ import annotations
import logging

from typing import Dict, List

from orchestrator.critic import Critic
from orchestrator.models import PlanResult, PlanStep, StepResult, RunContext, \
  RunStatus

from orchestrator.planner import Planner
from orchestrator.prompting.renderer import summarize_previous_results
from orchestrator.router import ExecutorRouter
from orchestrator.executors.base import BaseExecutor

log = logging.getLogger(__name__)

class Orchestrator:
  """
  Orchestrator v0 — minimal execution kernel.

  Responsibilities:
  - invoke planner
  - iterate over plan steps
  - route each step to executor
  - critic loop: retry if critic not approve
  - collect results

  - no hooks / events
  - no persistence
  """

  def __init__(
      self,
      *,
      planner: Planner,
      executors: Dict[str, BaseExecutor],
      router: ExecutorRouter,
      critic: Critic,
      max_retries: int = 3,
  ):
    self._planner = planner
    self._executors = executors
    self._router = router
    self._critic = critic
    self._max_retries = max_retries

  async def run(self, user_request: str) -> RunContext:
    """
      Full execution pipeline:

      Args:
          user_request: raw user input

      Returns:
          List[StepResult]
      """

    ctx = RunContext(user_request=user_request, max_retries=self._max_retries)

    log.info("Start execute request: `%s`", user_request)

    # 1. Planning
    plan: PlanResult = await self._planner.plan(user_request,
                                                ctx.critic_feedback,
                                                attempt=1)
    ctx.plan = plan

    log.debug("Plan: `%s`", ctx.plan)

    # 2. Execution loop
    for step in plan.steps:
      step_retry_count = 0
      ctx.status = RunStatus.FAIL

      # For each cycle we retry until step_result == SUCCESS
      while step_retry_count < ctx.max_retries:
        step_retry_count = step_retry_count + 1

        log.debug("Step: `%d`, plan: `%s`", step_retry_count, ctx.plan)

        step_result = await self._execute_step(step, previous_results=ctx.step_results)
        ctx.step_results.append(step_result)

        # 3. Review each step result with Critic
        critic_result = await self._critic.review(step, step_result)
        ctx.critic_feedback = critic_result

        # Breaking repeating step if the critic approved step
        if critic_result.approved:
          ctx.status = RunStatus.SUCCESS
          log.debug("Step: `%d`, `%s`", step_retry_count, RunStatus.SUCCESS)
          break

    log.info("Finish execute request: `%s` with status: `%s`", user_request, ctx.status)
    return ctx

  async def _execute_step(self, step: PlanStep,
      previous_results: List[StepResult]) -> StepResult:
    """
    Execute a single step via routed executor.
    """

    # 1. Resolve executor type
    executor_type = self._router.route(step)

    # 2. Get executor instance
    try:
      executor = self._executors[executor_type]
    except KeyError:
      raise ValueError(f"No executor registered for type: {executor_type}")

    # 3. Execute
    previous_results_text = summarize_previous_results(previous_results)
    return await executor.execute(step, previous_results=previous_results_text)
