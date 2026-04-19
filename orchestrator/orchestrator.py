from __future__ import annotations

from typing import Dict, List

from orchestrator.critic import Critic
from orchestrator.models import PlanResult, PlanStep, StepResult, RunContext

from orchestrator.planner import Planner
from orchestrator.prompting.renderer import summarize_previous_results
from orchestrator.router import ExecutorRouter
from orchestrator.executors.base import BaseExecutor


class Orchestrator:
    """
    Orchestrator v0 — minimal execution kernel.

    Responsibilities:
    - invoke planner
    - iterate over plan steps
    - route each step to executor
    - collect results

    Non-responsibilities (intentionally excluded in v0):
    - no retry logic
    - no critic loop
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

    async def run(self, user_request: str) -> List[StepResult]:
      """
        Full execution pipeline:

        Args:
            user_request: raw user input

        Returns:
            List[StepResult]
        """

      ctx = RunContext(user_request=user_request, max_retries=self._max_retries)
      while ctx.retry_count <= ctx.max_retries:

        # 1. Planning
        plan: PlanResult = await self._planner.plan(user_request, ctx.critic_feedback, attempt=ctx.retry_count)
        ctx.step_results = []
        rejected = False

        # 2. Execution loop
        for step in plan.steps:
            result = await self._execute_step(step, previous_results=ctx.step_results)
            ctx.step_results.append(result)

            # 3. Review each step result with Critic
            critic_result = await self._critic.review(step, result)
            if not critic_result.approved:
              ctx.critic_feedback = critic_result
              ctx.retry_count += 1
              rejected = True
              break

        if not rejected:
          return ctx.step_results  # all steps approved

      return ctx.step_results  # max retries exhausted

    async def _execute_step(self, step: PlanStep, previous_results: List[StepResult]) -> StepResult:
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
