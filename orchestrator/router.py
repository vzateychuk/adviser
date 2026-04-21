from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from orchestrator.models import PlanStep


ExecutorKey = Literal["generic", "code"]


@dataclass(frozen=True)
class RouteDecision:
  """
  Result of routing a PlanStep to an executor.
  """
  executor_key: ExecutorKey


# Domain-level step types (already introduced earlier)
StepType = Literal["generic", "code"]

class ExecutorRouter:
    """
    Determines which executor should handle a given PlanStep.

    Design constraints (v0):
    - No LLM usage
    - No heuristics on natural language
    - No dependency on CLI or config
    - Pure function of PlanStep

    Future extensions:
    - fallback routing (on review reject)
    - capability-based routing
    """

    def route(self, step: PlanStep) -> StepType:
        """
        Select executor type based on step.type.

        Raises:
            ValueError: if step.type is unsupported
        """
        step_type = step.type

        if step_type == "generic":
            return "generic"

        if step_type == "code":
            return "code"

        raise ValueError(f"Unsupported step.type: {step_type}")