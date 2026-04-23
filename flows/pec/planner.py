from __future__ import annotations

import logging
from typing import Any

from flows.pec.models import PlanResult
from flows.pec.renderer import render_planner_prompt
from flows.pec.schema_catalog import SchemaCatalog
from flows.pec.yaml_utils import load_llm_yaml
from llm.protocol import LLMClient
from llm.types import ChatRequest, Message

log = logging.getLogger(__name__)

_DEFAULT_SUCCESS_CRITERIA = {
    "lab": [
        "Preserve all dates exactly as written.",
        "Preserve all numeric values exactly as written.",
        "Preserve all measurement units exactly as written.",
        "Preserve analyte names and reference ranges exactly as written.",
    ],
    "diagnostic": [
        "Preserve all dates exactly as written.",
        "Preserve all measurements exactly as written.",
        "Preserve all conclusions and findings exactly as written.",
    ],
    "consultation": [
        "Preserve all dates exactly as written.",
        "Preserve all physician conclusions exactly as written.",
        "Preserve all diagnoses, recommendations, and medications exactly as written.",
    ],
    "medication_trace": [
        "Preserve all dates exactly as written.",
        "Preserve all medication names and dosages exactly as written.",
        "Preserve all frequency and duration information exactly as written.",
    ],
}


class Planner:
    """Builds a medical extraction plan from document text and LLM output.

    It exists to triage the document, choose a canonical schema id, and shape a
    minimal plan that downstream executor and critic stages can rely on.
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
        """Ask the LLM for a plan and repair near-valid output into a usable result.

        The planner is intentionally tolerant to small LLM deviations because a
        near-correct plan is often good enough once schema and step fields are fixed.
        """

        user_prompt = render_planner_prompt(
            user_request=user_request,
            document_content=document_content,
            schema_catalog_summary=self._schema_catalog.prompt_summary(),
            template=self._user_template,
        )
        resp = await self._llm.chat(
            ChatRequest(
                messages=[
                    Message(role="system", content=self._system_prompt),
                    Message(role="user", content=user_prompt),
                ],
            )
        )
        log.debug("Planner response text:\n%s", resp.text)
        data = self._repair_planner_payload(load_llm_yaml(resp.text), document_content=document_content)
        plan = PlanResult.model_validate(data)
        if plan.schema_name and not self._schema_catalog.has(plan.schema_name):
            raise ValueError(f"Planner selected unknown schema: {plan.schema_name}")
        return plan

    def _repair_planner_payload(self, data: dict[str, Any], *, document_content: str) -> dict[str, Any]:
        """Normalize planner YAML so downstream code sees canonical schema and steps.

        We repair small issues here to avoid failing the whole flow on alias names,
        uppercase step types, missing outputs, or empty criteria that are easy to fix.
        """

        repaired = dict(data)

        action = str(repaired.get("action", "PLAN")).strip().upper()
        if action not in {"PLAN", "SKIP"}:
            action = "PLAN"
        repaired["action"] = action

        if action == "SKIP":
            repaired["schema_name"] = None
            repaired["steps"] = []
            return repaired

        schema_name = self._schema_catalog.resolve_schema_id(repaired.get("schema_name"))
        if schema_name is None:
            raise ValueError(
                f"Planner selected unknown schema: {repaired.get('schema_name')!r}. "
                f"Allowed: {', '.join(self._schema_catalog.ids())}"
            )
        repaired["schema_name"] = schema_name

        steps = repaired.get("steps") or []
        repaired["steps"] = [self._repair_step(step, schema_name) for step in steps if isinstance(step, dict)]
        if not repaired["steps"]:
            repaired["steps"] = [self._default_step(schema_name=schema_name, document_content=document_content)]
        return repaired

    def _repair_step(self, step: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Repair a single step by enforcing canonical type, output, and criteria.

        This keeps the plan executable even when the LLM omits fields that can be
        reconstructed from the selected schema.
        """

        repaired = dict(step)
        repaired["type"] = str(repaired.get("type", "ocr")).strip().lower() or "ocr"
        repaired["output"] = schema_name
        if not repaired.get("input"):
            repaired["input"] = "document_content"
        if not repaired.get("title"):
            repaired["title"] = f"Extract {schema_name} data"
        criteria = repaired.get("success_criteria") or []
        if not criteria:
            repaired["success_criteria"] = list(_DEFAULT_SUCCESS_CRITERIA.get(schema_name, [])) or [
                "Preserve all visible values exactly as written."
            ]
        return repaired

    def _default_step(self, *, schema_name: str, document_content: str) -> dict[str, Any]:
        """Create a fallback step when the LLM returns a plan without steps.

        A minimal step is preferable to a hard failure because it allows the
        pipeline to continue and produce an actionable extraction attempt.
        """

        _ = document_content  # reserved for future smarter derivation
        return {
            "id": 1,
            "title": f"Extract {schema_name} data",
            "type": "ocr",
            "input": "document_content",
            "output": schema_name,
            "success_criteria": list(_DEFAULT_SUCCESS_CRITERIA.get(schema_name, []))
            or ["Preserve all visible values exactly as written."],
        }
