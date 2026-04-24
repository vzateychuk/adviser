from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from flows.pec.models import PlanAction, PlanResult, PlanStep, StepType
from flows.pec.renderer import render_planner_prompt
from flows.pec.schema_catalog import SchemaCatalog
from llm.errors import StructuredOutputError
from llm.protocol import LLMClient
from common.types import ChatRequest, Message

log = logging.getLogger(__name__)


# =============================================================================
# PLANNER OUTPUT SCHEMA (optimized for instructor)
# =============================================================================


class PlanStepSchema(BaseModel):
    """Single extraction step in the plan.

    Field descriptions are injected into the JSON schema by instructor,
    improving LLM compliance with the expected format.
    """

    id: int = Field(
        ge=1,
        description="Step number starting from 1",
    )
    title: str = Field(
        min_length=1,
        description="Step title. Example: 'Extract laboratory panel data'",
    )
    type: StepType = Field(
        default=StepType.OCR,
        description="Always 'ocr' for document extraction",
    )
    input: str = Field(
        min_length=1,
        description="Input source. Use 'document_content' for the full document",
    )
    output: str = Field(
        min_length=1,
        description="Must match schema_name exactly (e.g., 'lab', 'consultation')",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description=(
            "Verification criteria for the Critic. "
            "If empty, defaults will be loaded from the schema catalog."
        ),
    )


class PlannerOutputSchema(BaseModel):
    """Structured output schema for the Planner LLM call.

    This schema is passed to instructor which injects it as JSON schema
    into the API call. Field descriptions guide the LLM toward correct output.

    Design notes:
    - We use a separate schema from PlanResult to keep LLM-facing and
      internal representations decoupled
    - Descriptions are optimized for LLM understanding, not code docs
    - Validators run after LLM output is parsed, catching edge cases
    """

    action: Literal["PLAN", "SKIP"] = Field(
        description=(
            "PLAN to process the document and extract data. "
            "SKIP if not a medical document or cannot be extracted."
        ),
    )
    goal: str = Field(
        default="",
        description=(
            "Brief extraction goal description. "
            "Required when action=PLAN. Example: 'Extract laboratory panel results'"
        ),
    )
    schema_name: str | None = Field(
        default=None,
        description=(
            "Exactly one of: 'lab', 'diagnostic', 'consultation', 'medication_trace'. "
            "Required when action=PLAN. Must be null when action=SKIP."
        ),
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made during triage (e.g., 'Document is in Russian', 'Contains blood test results')",
    )
    steps: list[PlanStepSchema] = Field(
        default_factory=list,
        description="Extraction steps (required when action=PLAN, empty when action=SKIP)",
    )

    @model_validator(mode="after")
    def validate_plan_skip_consistency(self) -> "PlannerOutputSchema":
        """Ensure PLAN has required fields and SKIP has none.
        
        This validator gives instructor clear error messages for retries.
        """
        if self.action == "PLAN":
            if not self.goal or not self.goal.strip():
                raise ValueError("goal is required when action=PLAN")
            if not self.schema_name or not self.schema_name.strip():
                raise ValueError("schema_name is required when action=PLAN")
            if not self.steps:
                raise ValueError("steps must not be empty when action=PLAN")
        else:  # SKIP
            if self.steps:
                raise ValueError("steps must be empty when action=SKIP")
        return self

    def to_plan_result(self) -> PlanResult:
        """Convert LLM output schema to internal PlanResult domain model."""
        return PlanResult(
            goal=self.goal,
            action=PlanAction(self.action),
            schema_name=self.schema_name,
            assumptions=self.assumptions,
            steps=[
                PlanStep(
                    id=step.id,
                    title=step.title,
                    type=step.type,
                    input=step.input,
                    output=step.output,
                    success_criteria=step.success_criteria,
                )
                for step in self.steps
            ],
        )


# =============================================================================
# PLANNER
# =============================================================================


class Planner:
    """Builds a medical extraction plan using structured LLM output.

    The Planner:
    1. Triages the document to determine if it's processable
    2. Selects the appropriate extraction schema from the catalog
    3. Generates extraction steps with success criteria

    Uses instructor for structured outputs — no manual JSON/YAML parsing.
    All parsing, validation, and retry logic is delegated to the LLM adapter.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        system_prompt: str,
        user_template: str,
        schema_catalog: SchemaCatalog,
    ):
        self._llm = llm
        self._system_prompt = system_prompt
        self._user_template = user_template
        self._schema_catalog = schema_catalog

    async def plan(self, *, user_request: str, document_content: str) -> PlanResult:
        """Generate an extraction plan using structured LLM output.

        The method:
        1. Renders the prompt with document content and schema catalog
        2. Calls LLM with PlannerOutputSchema as response_model
        3. Validates schema selection against the catalog
        4. Applies post-processing repairs (default criteria, schema normalization)

        Args:
            user_request: Original user request or document path
            document_content: Full text content of the document

        Returns:
            Validated PlanResult ready for executor

        Raises:
            StructuredOutputError: LLM failed to produce valid output after retries
            ValueError: Selected schema not in catalog
        """
        user_prompt = render_planner_prompt(
            user_request=user_request,
            document_content=document_content,
            schema_catalog_summary=self._schema_catalog.prompt_summary(),
            template=self._user_template,
        )

        log.debug("Planner.plan: calling LLM with structured output")

        try:
            output = await self._llm.chat_structured(
                ChatRequest(
                    messages=[
                        Message(role="system", content=self._system_prompt),
                        Message(role="user", content=user_prompt),
                    ],
                ),
                response_model=PlannerOutputSchema,
            )
        except StructuredOutputError as e:
            log.error("Planner failed to produce valid output: %s", e)
            raise

        log.debug("Planner raw output: action=%s, schema=%s", output.action, output.schema_name)

        # Post-process: normalize schema name and apply defaults
        plan = self._post_process(output, document_content=document_content)

        log.info(
            "Planner result: action=%s, schema=%s, steps=%d",
            plan.action.value,
            plan.schema_name,
            len(plan.steps),
        )
        return plan

    def _post_process(self, output: PlannerOutputSchema, *, document_content: str) -> PlanResult:
        """Apply post-processing repairs to the structured output.

        Even with structured outputs, we still need some normalization:
        - Resolve schema aliases to canonical IDs
        - Inject default success criteria when LLM omits them
        - Generate fallback step if LLM returns empty steps for PLAN action

        This keeps the Planner tolerant to minor LLM deviations while
        delegating heavy parsing to instructor.
        """
        # Handle SKIP action
        if output.action == "SKIP":
            return PlanResult(
                goal=output.goal or "Document skipped",
                action=PlanAction.SKIP,
                schema_name=None,
                assumptions=output.assumptions,
                steps=[],
            )

        # Resolve schema alias to canonical ID
        schema_name = self._schema_catalog.resolve_schema_id(output.schema_name)
        if schema_name is None:
            raise ValueError(
                f"Planner selected unknown schema: {output.schema_name!r}. "
                f"Allowed: {', '.join(self._schema_catalog.ids())}"
            )

        # Get default criteria from schema catalog
        schema_def = self._schema_catalog.get(schema_name)
        default_criteria = schema_def.critic_rules or ["Preserve all values exactly as written."]

        # Process steps with default criteria injection
        steps: list[PlanStep] = []
        for step in output.steps:
            criteria = step.success_criteria if step.success_criteria else default_criteria

            steps.append(
                PlanStep(
                    id=step.id,
                    title=step.title or f"Extract {schema_name} data",
                    type=step.type,
                    input=step.input or "document_content",
                    output=schema_name,  # Always use resolved schema name
                    success_criteria=criteria,
                )
            )

        # Steps are required for PLAN action
        if not steps:
            raise ValueError(
                f"Planner returned action=PLAN but no steps. "
                f"This indicates an LLM error. schema_name={schema_name!r}"
            )

        return PlanResult(
            goal=output.goal,
            action=PlanAction.PLAN,
            schema_name=schema_name,
            assumptions=output.assumptions,
            steps=steps,
        )
