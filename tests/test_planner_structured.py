"""Tests for Planner with structured outputs."""
from __future__ import annotations

import pytest

from flows.pec.models import PlanAction, RunStatus
from flows.pec.planner import Planner, PlannerOutputSchema, PlanStepSchema, StepType
from flows.pec.schema_catalog import SchemaCatalog
from llm.mock import MockLLMClient
from common.types import ChatRequest


# =============================================================================
# FIXTURES
# =============================================================================


def mock_planner_structured(req: ChatRequest, response_model: type) -> PlannerOutputSchema:
    """Mock scenario for Planner structured output."""
    user_content = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    
    if "skip" in user_content.lower() or "not medical" in user_content.lower():
        return PlannerOutputSchema(
            action="SKIP",
            goal="Document is not medical",
            schema_name=None,
            steps=[],
        )
    
    return PlannerOutputSchema(
        action="PLAN",
        goal="Extract lab results",
        schema_name="lab",
        steps=[
            PlanStepSchema(
                id=1,
                title="Extract laboratory panel",
                type=StepType.OCR,
                input="document_content",
                output="lab",
                success_criteria=[
                    "Preserve all dates exactly as written",
                    "Preserve all numeric values exactly as written",
                    "Preserve all measurement units exactly as written",
                ],
            )
        ],
    )


@pytest.fixture
def mock_llm() -> MockLLMClient:
    """Create a mock LLM client with structured planner scenario."""
    return MockLLMClient(
        model_alias="test-model",
        planner_structured=mock_planner_structured,
    )


@pytest.fixture
def schema_catalog(tmp_path) -> SchemaCatalog:
    """Create a minimal schema catalog for testing."""
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    
    # Create a minimal lab schema
    lab_schema = schema_dir / "lab.yaml"
    lab_schema.write_text("""
schema_meta:
  id: lab
  title: Laboratory Results
  category: lab
selection_hints:
  aliases: [laboratory, blood_test]
  key_signals: [hemoglobin, glucose]
extraction_contract:
  required_blocks: [patient, results]
critic_rules:
  must_verify: [all values preserved]
""")
    
    # Create a minimal consultation schema
    consultation_schema = schema_dir / "consultation.yaml"
    consultation_schema.write_text("""
schema_meta:
  id: consultation
  title: Medical Consultation
  category: consultation
selection_hints:
  aliases: [visit, outpatient]
  key_signals: [diagnosis, recommendation]
extraction_contract:
  required_blocks: [patient, findings]
critic_rules:
  must_verify: [conclusions preserved]
""")
    
    return SchemaCatalog(schema_dir)


@pytest.fixture
def planner(mock_llm: MockLLMClient, schema_catalog: SchemaCatalog) -> Planner:
    """Create a Planner with mock LLM and schema catalog."""
    return Planner(
        llm=mock_llm,
        system_prompt="Role: Planner\nYou are a medical document planner.",
        user_template="Document: {{DOCUMENT_CONTENT}}\nCatalog: {{SCHEMA_CATALOG}}",
        schema_catalog=schema_catalog,
    )


# =============================================================================
# TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_planner_returns_plan_result(planner: Planner):
    """Planner should return a valid PlanResult for medical documents."""
    result = await planner.plan(
        user_request="extract_lab.pdf",
        document_content="Hemoglobin: 140 g/L",
    )
    
    assert result.action == PlanAction.PLAN
    assert result.schema_name == "lab"
    assert len(result.steps) == 1
    assert result.steps[0].type == StepType.OCR


@pytest.mark.asyncio
async def test_planner_skips_non_medical(planner: Planner):
    """Planner should return SKIP for non-medical documents."""
    result = await planner.plan(
        user_request="shopping_list.txt",
        document_content="This is not medical. Skip it.",
    )
    
    assert result.action == PlanAction.SKIP
    assert result.schema_name is None
    assert result.steps == []


@pytest.mark.asyncio
async def test_planner_has_success_criteria(planner: Planner):
    """Planner should include success criteria in steps."""
    result = await planner.plan(
        user_request="lab_results.pdf",
        document_content="Glucose: 5.5 mmol/L",
    )
    
    assert result.steps[0].success_criteria
    assert len(result.steps[0].success_criteria) > 0


def test_planner_output_schema_to_plan_result():
    """PlannerOutputSchema should convert to PlanResult correctly."""
    schema = PlannerOutputSchema(
        action="PLAN",
        goal="Test goal",
        schema_name="lab",
        steps=[
            PlanStepSchema(
                id=1,
                title="Test step",
                type=StepType.OCR,
                input="doc",
                output="lab",
                success_criteria=["criteria 1"],
            )
        ],
    )
    
    result = schema.to_plan_result()
    
    assert result.goal == "Test goal"
    assert result.action == PlanAction.PLAN
    assert result.schema_name == "lab"
    assert len(result.steps) == 1
    assert result.steps[0].id == 1
