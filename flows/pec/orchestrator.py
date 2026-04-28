from __future__ import annotations

import logging

from flows.pec.critic import Critic
from flows.pec.models import OcrResult, PlanAction, RunContext, RunStatus
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
        
        All methods mutate the context in place. No reassignment needed.
        """
        runCtx = RunContext(user_request=file_path, document_content=doc_content)
        await self.plan(runCtx)
        
        if runCtx.status == RunStatus.SKIPPED:
            return OcrResult(
                document_path=file_path,
                schema_name=runCtx.active_schema,
                context="",
                step_results=runCtx.steps_results,
                retry_count=0,
                status=runCtx.status,
            )
        
        # 1. Execute all steps via executor (no critic)
        await self.execute(runCtx)
        
        # 2. Review all results via critic (mutates ctx in place)
        await self.critic(runCtx)
        
        return OcrResult(
            document_path=file_path,
            schema_name=runCtx.active_schema,
            context=runCtx.doc.model_dump_json() if runCtx.doc else "",
            step_results=runCtx.steps_results,
            retry_count=0,
            status=runCtx.status,
        )

    async def plan(self, runCtx: RunContext) -> None:
        """Populate the run context with planner output and derived schema state.
        Mutates the context in place.
        """
        plan = await self._planner.plan(
            user_request=runCtx.user_request,
            document_content=runCtx.document_content,
        )
        runCtx.plan = plan
        runCtx.active_schema = plan.schema_name
        runCtx.status = (
            RunStatus.SKIPPED if plan.action == PlanAction.SKIP else RunStatus.PLANNED
        )

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
            
            # Merge incrementally; result.doc is always non-None per Pydantic validation
            context.doc = context.doc.merge(result.doc) if context.doc else result.doc
        
        context.status = RunStatus.COMPLETED
        log.info("Executed %d steps", len(context.steps_results))


    async def critic(self, context: RunContext) -> None:
        """Review all executed steps sequentially, stopping on first failure.
        
        This method mutates the context in place, updating:
        - context.critic_feedback (list of issues if rejected)
        - context.status (FAILED if rejected, COMPLETED if all approved)
        
        Args:
            context: Shared run context with steps_results populated
            
        Raises:
            ValueError: If no steps_results are present
        """
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
                log.error(
                    "Step %d rejected: %s",
                    step_result.step_id,
                    verdict.summary,
                )
                return
            
            log.debug("Step %d approved", step_result.step_id)
        
        context.critic_feedback = []
        context.status = RunStatus.COMPLETED
        log.info("All %d steps approved", len(context.steps_results))
