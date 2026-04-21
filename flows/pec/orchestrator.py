from __future__ import annotations

import logging
from typing import List

from flows.pec.models import OcrResult, PlanStep, StepResult
from flows.pec.planner import Planner
from flows.pec.critic import Critic
from flows.pec.executors.ocr import OcrExecutor
from flows.pec.prompting.renderer import format_critic_feedback, summarize_previous_results

log = logging.getLogger(__name__)


class PecOrchestrator:
    """
    OCR PEC Orchestrator.

    Execution pipeline:
      1. Planner classifies the document and produces a plan (1-2 steps).
      2. For each step:
         a. OcrExecutor extracts structured YAML data.
         b. Critic validates the result against success_criteria.
         c. On rejection: retry with Critic feedback (up to max_retries).
      3. Returns OcrResult to the Coordinator.

    Coordinator is responsible for persisting the result (GitHub/storage).
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

    async def run(self, file_path: str, doc_context: str = "") -> OcrResult:
        """
        Full OCR pipeline: Plan -> Execute -> Critic (retry loop).

        Args:
            file_path: path to the document to process
            doc_context: optional context hint from Coordinator (doc type, source, etc.)

        Returns:
            OcrResult with approved YAML content and execution metadata
        """
        user_request = f"file_path: {file_path}"
        if doc_context:
            user_request += f"\ncontext: {doc_context}"

        # 1. Plan
        plan = await self._planner.plan(user_request)
        log.info("Plan ready: goal=%r, schema=%r, steps=%d", plan.goal, plan.schema_name, len(plan.steps))

        if not plan.steps:
            raise ValueError("Planner returned an empty plan — nothing to execute.")

        completed: List[StepResult] = []
        total_retries = 0

        # 2. Execute each step with Critic loop
        for step in plan.steps:
            result, retries = await self._execute_with_review(step, completed)
            completed.append(result)
            total_retries += retries

        # 3. Build output — last step result holds the final YAML
        final_result = completed[-1]
        return OcrResult(
            document_path=file_path,
            schema_name=plan.schema_name,
            yaml_content=final_result.content,
            step_results=completed,
            retry_count=total_retries,
        )

    async def _execute_with_review(
        self,
        step: PlanStep,
        previous_results: List[StepResult],
    ) -> tuple[StepResult, int]:
        """
        Execute one step with Critic retry loop.

        Returns the accepted StepResult and the number of retries used.
        """
        previous_text = summarize_previous_results(previous_results)
        critic_feedback = ""
        retries = 0
        result: StepResult | None = None

        for attempt in range(self._max_retries + 1):
            result = await self._executor.execute(
                step,
                previous_results=previous_text,
                critic_feedback=critic_feedback,
            )

            verdict = await self._critic.review(step, result)

            if verdict.approved:
                log.info("Step %d approved on attempt %d.", step.id, attempt)
                return result, retries

            retries += 1
            if attempt < self._max_retries:
                critic_feedback = format_critic_feedback(verdict, attempt=attempt + 1)
                log.warning(
                    "Step %d rejected (attempt %d/%d): %s",
                    step.id, attempt + 1, self._max_retries, verdict.summary,
                )
            else:
                log.error(
                    "Step %d exhausted %d retries. Returning last result.",
                    step.id, self._max_retries,
                )

        return result, retries  # type: ignore[return-value]
