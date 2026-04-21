from __future__ import annotations
import logging

from typing import Dict, List

from orchestrator.reviewer import Reviewer
from orchestrator.models import ReviewResult, PlanResult, PlanStep, StepResult, RunContext, RunStatus

from orchestrator.planner import Planner
from orchestrator.prompting.renderer import summarize_previous_results
from orchestrator.router import ExecutorRouter
from orchestrator.executors.base import BaseExecutor

log = logging.getLogger(__name__)


class Orchestrator:
  """
  Orchestrator — execution kernel.

  Responsibilities:
  - invoke planner (once per run)
  - iterate over plan steps sequentially
  - route each step to the correct executor
  - review loop: retry failed step with review feedback injected into executor prompt
  - collect approved results

  - no hooks / events
  - no persistence
  """

  def __init__(
      self,
      *,
      planner: Planner,
      executors: Dict[str, BaseExecutor],
      router: ExecutorRouter,
      reviewer: Reviewer,
      max_retries: int = 3,
  ):
    self._planner = planner
    self._executors = executors
    self._router = router
    self._reviewer = reviewer
    self._max_retries = max_retries

  async def run(self, user_request: str) -> RunContext:
    """
    Full execution pipeline: Planner → (Executor → Reviewer) per step.

    Planner is called once. Each step may be retried up to max_retries times
    if Reviewer rejects it. On retry the executor receives the Reviewer's feedback
    so it can address the specific issues.

    Args:
        user_request: raw user input

    Returns:
        RunContext with plan, approved step results, retry count and final status
    """
    ctx = RunContext(user_request=user_request, max_retries=self._max_retries)

    log.info("Orchestrator.run started: %r", user_request)

    # 1. Plan once — review feedback drives executor retry, not re-planning
    ctx.plan = await self._planner.plan(user_request, attempt=0)

    log.debug("Plan ready: goal=%r, steps=%d", ctx.plan.goal, len(ctx.plan.steps))

    # 2. Execute each step with per-step retry loop
    for step in ctx.plan.steps:
      ctx.status = RunStatus.FAIL
      ctx.review_feedback = None               # reset: prior step's feedback is irrelevant
      attempt_results: List[StepResult] = []   # failed attempts for this step only

      for attempt in range(ctx.max_retries):
        # Approved results from prior steps + this step's failed attempts
        retry_context = ctx.step_results + attempt_results

        step_result = await self._execute_step(
            step,
            previous_results=retry_context,
            review_feedback=ctx.review_feedback,
        )
        log.debug("Step `%s` finished with result: `%s`, passing to reviewer", step.title, step.output)

        review_result = await self._reviewer.review(step, step_result)
        ctx.review_feedback = review_result

        if review_result.approved:
          ctx.step_results.append(step_result)   # only approved result enters ctx
          ctx.status = RunStatus.SUCCESS
          log.debug("Step id=%d approved on attempt=%d", step.id, attempt+1)
          break

        ctx.retry_count += 1
        attempt_results.append(step_result)
        log.debug("Step id=%d rejected on attempt=%d with summary: %s",step.id, attempt+1, review_result.summary)

    log.info("Orchestrator.run finished: status=%s retries=%d",ctx.status, ctx.retry_count,)
    return ctx

  async def _execute_step(
      self,
      step: PlanStep,
      previous_results: List[StepResult],
      review_feedback: ReviewResult | None = None,
  ) -> StepResult:
    """Execute a single step via routed executor."""

    executor_type = self._router.route(step)

    try:
      executor = self._executors[executor_type]
    except KeyError:
      raise ValueError(f"No executor registered for type: {executor_type}")

    previous_results_text = summarize_previous_results(previous_results)
    return await executor.execute(
        step,
        previous_results=previous_results_text,
        review_feedback=review_feedback,
    )
