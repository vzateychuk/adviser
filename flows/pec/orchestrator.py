from __future__ import annotations
import logging
from flows.pec.critic import Critic
from flows.pec.models import OcrResult, PlanAction, RunContext, RunStatus, StepResult
from flows.pec.ocr_executor import OcrExecutor
from flows.pec.planner import Planner

log = logging.getLogger(__name__)

class Orchestrator:
    """Coordinates the planner, executor, and critic through a shared run context.
    Orchestrator manages the workflow:
    - plan() — generates the plan.
    - execute() — runs steps (executor-only, no critic).
    - critic() — reviews results (critic-only).
    Retry logic is handled at the LLM Client level.
    """

    def __init__(
        self,
        *,
        planner: Planner,
        executor: OcrExecutor,
        critic: Critic,
    ):
        self._planner = planner
        self._executor = executor
        self._critic = critic

    async def run(self, file_path: str, doc_content: str = "") -> OcrResult:
        """Execute the full PEC pipeline and return the final OCR artifact.
        This is the end-to-end entry point used when callers want one process to handle planning, extraction, review, and final result assembly.
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

        # 1. Execute all steps via executor (no critic)
        await self.execute(ctx)

        # 2. Review all results via critic
        ctx = await self.critic(ctx)
        return OcrResult(
            document_path=file_path,
            schema_name=ctx.active_schema,
            context=ctx.doc.model_dump_json() if ctx.doc else "",
            step_results=ctx.steps_results,
            retry_count=0,
            status=ctx.status,
        )

    async def plan(self, ctx: RunContext) -> RunContext:
        """Populate the run context with planner output and derived schema state."""
        plan = await self._planner.plan(
            user_request=ctx.user_request,
            document_content=ctx.document_content,
        )
        ctx.plan = plan
        ctx.active_schema = plan.schema_name
        ctx.status = RunStatus.SKIPPED if plan.action == PlanAction.SKIP else RunStatus.PLANNED
        return ctx

    async def execute(self, context: RunContext) -> None:
        """Execute all planned steps WITHOUT critic, with retry logic delegated to transport layer."""
        if context.plan is None:
            raise ValueError("RunContext.plan is required for execution")
        if context.plan.action == PlanAction.SKIP:
            context.status = RunStatus.SKIPPED
            return

        for step in context.plan.steps:
            step_id = step.id
            log.info("Executing step %d: %s", step_id, step.title)
            result = await self._executor.execute(context, step_id)
            context.steps_results.append(result)

            # Incremental merge into accumulated doc
            if result.doc is not None:
                if context.doc is None:
                    context.doc = result.doc
                else:
                    context.doc = context.doc.merge(result.doc)

        context.status = RunStatus.COMPLETED
        log.info("Executed %d steps", len(context.steps_results))

    async def critic(self, context: RunContext) -> RunContext:
        """Review all executed steps sequentially, stopping on first failure."""
        if context.plan is None:
            raise ValueError("RunContext.plan is required for review")
        if not context.steps_results:
            raise ValueError("No step results to review")

        for step_result in context.steps_results:
            log.debug("Reviewing step %d", step_result.step_id)
            verdict = await self._critic.review(context, step_result)
            if not verdict.approved:
                context.critic_feedback = verdict.issues
                context.status = RunStatus.FAILED
                log.error("Step %d rejected: %s",