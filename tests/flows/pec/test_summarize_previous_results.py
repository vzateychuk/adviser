from flows.pec.models import StepResult
from flows.pec.renderer import summarize_previous_results



def test_summarize_previous_results_limits_lines():
    from flows.pec.models import MedicalDoc, DocumentInfo, PatientInfo
    doc = MedicalDoc(
        schema_id="lab",
        document=DocumentInfo(date="2024-01-01"),
        patient=PatientInfo(full_name="Test Patient"),
    )
    out = summarize_previous_results(doc, max_fields=5)
    assert "schema_id: lab" in out
    assert "patient.full_name: Test Patient" in out
