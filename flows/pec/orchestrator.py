from __future__ import annotations

import logging

from flows.pec.critic import Critic
from flows.pec.models import OcrResult, PlanAction, RunContext, RunStatus, StepResult
from flows.pec.ocr_executor import OcrExecutor
from flows.pec.planner import Planner

log = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates planner, executor, and critic through shared run state.

    The orchestrator owns the workflow policy because it is responsible for when
    to plan, retry, skip, and mark a run as finished or failed.
    """

    def __init__(
        self,
        *,
        planner: Planner,
        executor: OcrExecutor,
        critic: Critic,
        max_retries: int = 3,
    ):
        self._planner = planner
        self._executor = executor
        self._critic = critic
        self._max_retries = max_retries

    async def run(self, file_path: str, doc_content: str = "") -> OcrResult:
        """Execute the full PEC pipeline and return the final OCR artifact.

        This is the end-to-end entry point used when callers want one process to
        handle planning, extraction, review, retries, and final result assembly.
        """

        ctx = RunContext(user_request=file_path, document_content=doc_content)
        ctx = await self.plan(ctx)
        if ctx.status == RunStatus.SKIPPED:
            return OcrResult(
                document_path=file_path,
                schema_name=ctx.active_schema,
                context="",
                step_results=ctx.steps_results,
                retry_count=0,
                status=ctx.status,
            )

        total_retries = await self.execute(ctx)
        return OcrResult(
            document_path=file_path,
            schema_name=ctx.active_schema,
            context=ctx.doc.model_dump_json() if ctx.doc else "",
            step_results=ctx.steps_results,
            retry_count=total_retries,
            status=ctx.status,
        )

    async def plan(self, ctx: RunContext) -> RunContext:
        """Populate the run context with planner output and derived schema state.

        This is split out so the CLI can run planning in isolation while still
        using the same orchestration code as the full pipeline.
        """

        plan = await self._planner.plan(
            user_request=ctx.user_request,
            document_content=ctx.document_content,
        )
        ctx.plan = plan
        ctx.active_schema = plan.schema_name
        ctx.status = RunStatus.SKIPPED if plan.action == PlanAction.SKIP else RunStatus.PLANNED
        return ctx

    async def execute(self, context: RunContext) -> int:
        """
        Execute all planned steps and advance the run toward completion.

        Keeping this separate from planning makes debug workflows easier and lets
        isolated CLI commands reuse the exact same execution policy.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for execution")
        if context.plan.action == PlanAction.SKIP:
            context.status = RunStatus.SKIPPED
            return 0

        total_retries = 0
        for step in context.plan.steps:
            accepted, retries = await self._execute_with_review(context, step.id)
            context.steps_results.append(accepted)

            # Incremental merge into accumulated doc
            if accepted.doc is not None:
                context.doc = accepted.doc if context.doc is None else context.doc.merge(accepted.doc)

            context.critic_feedback = []
            total_retries += retries
        context.status = RunStatus.COMPLETED
        return total_retries

    async def review_context(self, context: RunContext) -> RunContext:
        """Run the critic on the latest result and update the run verdict.

        This entry point exists so review can be debugged independently from the
        executor and so rejection reasons can be inspected without rerunning work.
        """

        if context.plan is None:
            raise ValueError("RunContext.plan is required for review")
        if not context.steps_results:
            raise ValueError("RunContext.steps_results must contain at least one result for review")
        latest = context.steps_results[-1]
        verdict = await self._critic.review(context, latest.step_id, latest)
        context.critic_feedback = verdict.issues
        context.status = RunStatus.COMPLETED if verdict.approved else RunStatus.FAILED
        return context

    async def _execute_with_review(self, context: RunContext, step_id: int) -> tuple[StepResult, int]:
        """Run one step with critic-driven retries until approval or exhaustion.

        This retry loop belongs in the orchestrator because it is workflow policy,
        not executor or critic logic.
        """

        retries = 0
        # result: StepResult | None = None
        context.status = RunStatus.EXECUTING

        for attempt in range(self._max_retries + 1):
            result = await self._executor.execute(context, step_id)
            verdict = await self._critic.review(context, step_id, result)
            if verdict.approved:
                return result, retries
            context.critic_feedback = verdict.issues
            retries += 1
            if attempt >= self._max_retries:
                context.status = RunStatus.FAILED
                raise ValueError(f"Step {step_id} exhausted {self._max_retries} retries: {verdict.summary}")

        raise AssertionError("unreachable")
