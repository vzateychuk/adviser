from __future__ import annotations

import logging

import yaml
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
        max_retries,
    ):
        self._planner = planner
        self._executor = executor
        self._critic = critic
        self._max_retries = max_retries

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
        
        retry_count = 0
        for attempt in range(self._max_retries + 1):
            log.info(
                "PEC attempt %d/%d started",
                attempt + 1,
                self._max_retries + 1,
            )
            if attempt > 0:
                retry_count += 1
                log.info(
                    "Critic rejected, retry %d/%d",
                    retry_count,
                    self._max_retries,
                )
                # Reset extraction result so the next execute() starts clean.
                # critic_feedback is intentionally kept from the previous round:
                # the executor needs it to know exactly what to fix.
                # summarize_previous_results() returns "" when doc is None,
                # so no stale extraction leaks into the retry prompt.
                runCtx.doc = None

            await self.execute(runCtx)
            await self.critic(runCtx)

            if runCtx.status == RunStatus.COMPLETED:
                log.info(
                    "Critic approved on attempt %d/%d",
                    attempt + 1,
                    self._max_retries + 1,
                )
                break

            issues = runCtx.critic_feedback
            high = sum(1 for i in issues if i.severity == "high")
            medium = sum(1 for i in issues if i.severity == "medium")
            low = sum(1 for i in issues if i.severity == "low")
            log.warning(
                "Critic rejected on attempt %d/%d: %d issues (high=%d, medium=%d, low=%d)",
                attempt + 1,
                self._max_retries + 1,
                len(issues),
                high,
                medium,
                low,
            )
            for issue in issues:
                log.debug("  [%s] %s", issue.severity, issue.description)
        else:
            log.error(
                "PEC pipeline exhausted all %d attempts, status=%s",
                self._max_retries + 1,
                runCtx.status,
            )

        if runCtx.doc:
            doc_dict = doc_dict = runCtx.doc.model_dump()
            context = yaml.safe_dump(doc_dict, allow_unicode=True, sort_keys=False)
        else:
            context = ""
        return OcrResult(
            document_path=file_path,
            schema_name=runCtx.active_schema,
            context=context,
            step_results=runCtx.steps_results,
            retry_count=retry_count,
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
