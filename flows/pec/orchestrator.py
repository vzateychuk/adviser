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

    async def execute(self, runCtx: RunContext) -> None:
        """Execute all planned steps WITHOUT critic, with retry logic delegated to transport layer."""
        if runCtx.plan is None:
            raise ValueError("RunContext.plan is required for execution")
        
        if runCtx.plan.action == PlanAction.SKIP:
            runCtx.status = RunStatus.SKIPPED
            return
        
        for step in runCtx.plan.steps:
            step_id = step.id
            log.info("Executing step %d: %s", step_id, step.title)
            result = await self._executor.execute(runCtx, step_id)
            runCtx.steps_results.append(result)
            
            # Merge incrementally; result.doc is always non-None per Pydantic validation
            runCtx.doc = runCtx.doc.merge(result.doc) if runCtx.doc else result.doc
        
        runCtx.status = RunStatus.COMPLETED
        log.info("Executed %d steps", len(runCtx.steps_results))

    async def critic(self, runCtx: RunContext) -> None:
        """Review the final merged document - one call after all steps.

        This method mutates the context in place, updating:
        - runCtx.critic_feedback (list of issues if rejected)
        - runCtx.status (FAILED if rejected, COMPLETED if approved)

        Args:
            runCtx: Shared run context with doc (merged) populated

        Raises:
            ValueError: If no plan or doc is present
        """
        if runCtx.plan is None:
            raise ValueError("RunContext.plan is required for review")

        if runCtx.doc is None:
            raise ValueError("RunContext.doc is required for review")

        verdict = await self._critic.review(runCtx)

        runCtx.critic_feedback = verdict.issues
        runCtx.status = RunStatus.COMPLETED if verdict.approved else RunStatus.FAILED

        if verdict.approved:
            log.info("Critic approved")
        else:
            for issue in verdict.issues:
                log.error("  [%s] %s — %s", issue.severity, issue.description, issue.suggestion)
