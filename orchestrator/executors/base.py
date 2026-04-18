from __future__ import annotations

from abc import ABC, abstractmethod

from orchestrator.models import PlanStep, StepResult

class BaseExecutor(ABC):
    """
    Base contract for all executors.

    Design goals:
    - uniform interface across executor types
    - no orchestration logic here
    - no routing logic here
    - no knowledge of Planner or Orchestrator

    Each executor is responsible only for executing a single PlanStep.
    """

    def __init__(
        self,
        *,
        llm,
        model_name: str,
        system_prompt: str,
        user_template: str,
    ):
        """
        Args:
            llm: LLM client (transport abstraction)
            model_name: resolved model alias (from composition root)
            system_prompt: executor system prompt
            user_template: executor user prompt template
        """
        self._llm = llm
        self._model_name = model_name
        self._system_template = system_prompt
        self._user_template = user_template

    @abstractmethod
    async def execute(self, step: PlanStep, previous_results: str = "") -> StepResult:
        """
        Execute a single plan step.

        Args:
            step: PlanStep produced by Planner
            previous_results: rendered summary of prior step results

        Returns:
            StepResult: structured execution output
        """
        raise NotImplementedError
