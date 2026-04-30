# PEC Schema Catalog

YAML files in this directory serve a single purpose: **fuzzy matching** during the Planner phase. The Planner reads them to map a natural-language document description to a canonical schema ID (`lab`, `diagnostic`, `consultation`, `medication_trace`).

## What belongs here

Each YAML file contains:
- `schema_meta` — canonical ID, category, title, and intended_use examples that help the Planner pick the right schema for a given document
- `selection_hints.aliases` — alternative names the Planner or user may use (e.g. "анализы", "blood test" → `lab`)

## What does NOT belong here
- Extraction field templates — defined in `flows/pec/schemas/medical_doc.py` (`MedicalDoc` Pydantic model)
- Validation rules — generated per-document by the Planner as `PlanStep.success_criteria` and verified by the Critic

## Schema IDs

| ID | Typical documents |
|----|-------------------|
| `lab` | Blood panels, biochemistry, hormone tests, urinalysis |
| `diagnostic` | Ultrasound, X-ray, CT, MRI, imaging reports |
| `consultation` | Physician notes, specialist conclusions, outpatient visits |
| `medication_trace` | Prescriptions, medication lists, therapy history |
| `certificate` | Medical certificates, disability certificates |
| `epicrisis` | Discharge summaries, patient outcome summaries |
| `operation_protocol` | Surgical reports, operation protocols |

## Adding a new schema

1. Create `{schema_id}.yaml` with `schema_meta` and `selection_hints.aliases`
2. Add the new `schema_id` to the `Literal` type in `MedicalDoc.schema_id` (`flows/pec/schemas/medical_doc.py`)
3. Add schema-specific `success_criteria` hints to `prompts/planner/system.md`
