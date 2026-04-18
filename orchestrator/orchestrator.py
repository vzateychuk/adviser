from __future__ import annotations

from typing import Dict, List

from orchestrator.models import PlanResult, PlanStep, StepResult

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
    ):
        self._planner = planner
        self._executors = executors
        self._router = router

    async def run(self, user_request: str) -> List[StepResult]:
        """
        Full execution pipeline:

        1. Plan
        2. Execute steps sequentially
        3. Return step results

        Args:
            user_request: raw user input

        Returns:
            List[StepResult]
        """

        # -------------------------
        # 1. Planning
        # -------------------------
        plan: PlanResult = await self._planner.plan(user_request)

        # Defensive: ensure steps exist
        if not plan.steps:
            return []

        results: List[StepResult] = []

        # -------------------------
        # 2. Execution loop
        # -------------------------
        for step in plan.steps:
            result = await self._execute_step(step, previous_results=results)
            results.append(result)

        # -------------------------
        # 3. Return results
        # -------------------------
        return results

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
