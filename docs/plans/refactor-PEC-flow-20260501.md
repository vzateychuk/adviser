# PEC Flow Redesign: Execution Plan (Phase 1)

## Pre-checks (read-only, before any edits)

All files to be edited already exist. Current confirmed state:
- `OrchestratorConfig.max_retries` exists in `common/types.py:91-93`
- `AppConfig.orchestrator` exists in `common/types.py:104`
- `config/{dev,prod,test}/app.yaml` already have `orchestrator.max_retries` — NO changes needed
- `MedicalDoc.notes` is `list[str]` with working `normalize_notes` validator in `models.py:568-571` — NO changes needed (corruption was from multi-step merge, not the validator)

---

## Step 1 — `prompts/planner/system.md`

### Edit 1a: Replace Mandatory Step Structure rule with Step Generation Rule

Find EXACTLY this block (lines 22–41):

```
## Step Construction

When action is "PLAN", generate extraction steps using the **Mandatory Step Structure** below.

Steps are generated only for data that is actually present in the document. 
When multiple categories are present, they MUST appear:

**Patient demographics step (include only if patient section is present)**
- Extract: full name, date of birth, gender, patient ID, etc
- Skip entirely if the document contains no patient section

**Medical organization step (include only if organization section is present)**
- Extract: institution name, address, phone/website, department, registration or license number
- Skip entirely if the document contains no organization section

**Document-specific data steps (one or more, based on content)**
- One step per logical data group (e.g., one analyte group, one diagnosis block)
- Step title MUST name the specific data group:
  - Good: "Extract complete blood count analytes", "Extract primary diagnosis and ICD code"
  - Bad: "Extract lab data", "Extract information", "Extract document fields"
```

Replace with:

```
## Step Construction

When action is "PLAN", generate the minimum number of steps required.

**Step Generation Rule:**
- Generate ONE step when all needed data resides in a single document section.
- Generate 2–3 steps ONLY when the document has genuinely distinct sections
  (e.g., a multi-page lab report where demographics and analyte table are on separate pages).
- NEVER generate multiple steps that read from the same document section.
  Steps with identical input scope and identical output type MUST be merged into one.
```

### Edit 1b: Replace multi-step JSON example with single-step example

Find EXACTLY this block (lines 81–125):

```
Example for PLAN:
```json
{
  "action": "PLAN",
  "goal": "Extract complete blood count results from laboratory report",
  "schema_name": "lab",
  "steps": [
    {
      "id": 1,
      "title": "Extract patient demographics",
      "type": "ocr",
      "input": "document_content",
      "output": "lab",
      "success_criteria": [
        "Patient surname 'Иванов' preserved in extracted result",
        "Date of birth '15.04.1978' preserved in extracted result"
      ]
    },
    {
      "id": 2,
      "title": "Extract medical organization",
      "type": "ocr",
      "input": "document_content",
      "output": "lab",
      "success_criteria": [
        "Institution name 'ГБУЗ ГКБ №52' preserved in extracted result",
        "Field address must be null in extracted result — absent in source document"
      ]
    },
    {
      "id": 3,
      "title": "Extract complete blood count analytes",
      "type": "ocr",
      "input": "document_content",
      "output": "lab",
      "success_criteria": [
        "Hemoglobin value '142 г/л' preserved in extracted result",
        "Analysis date '12.03.2024' preserved in extracted result",
        "24 analytes present in source — all 24 must appear in extracted result",
        "No analyte invented or dropped"
      ]
    }
  ]
}
```
```

Replace with:

```
Example for PLAN:
```json
{
  "action": "PLAN",
  "goal": "Extract all medical entities from the laboratory report",
  "schema_name": "lab",
  "steps": [
    {
      "id": 1,
      "title": "Extract all entities from laboratory report",
      "type": "ocr",
      "input": "document_content",
      "output": "lab",
      "success_criteria": [
        "Patient surname 'Иванов' preserved in extracted result",
        "Date of birth '15.04.1978' preserved in extracted result",
        "Institution name 'ГБУЗ ГКБ №52' preserved in extracted result",
        "Field address must be null in extracted result — absent in source document",
        "Hemoglobin value '142 г/л' preserved in extracted result",
        "Analysis date '12.03.2024' preserved in extracted result",
        "24 analytes present in source — all 24 must appear in extracted result",
        "No analyte invented or dropped"
      ]
    }
  ]
}
```
```

---

## Step 2 — `prompts/ocr_executor/system.md`

### Edit 2a: Append Retry Mode block at end of file

Find EXACTLY the last line of the file:

```
- The JSON must be parseable without modification.
```

Replace with:

```
- The JSON must be parseable without modification.

## Retry Mode

When CRITIC_FEEDBACK is non-empty, this is a RETRY attempt.
The previous extraction was REJECTED. You MUST:
1. Read every issue in CRITIC_FEEDBACK before reading the document.
2. Fix EVERY listed issue exactly as suggested.
3. Do NOT modify fields not mentioned in the issues — preserve them as-is.
4. If an issue says a field is missing — find it in the document and add it.
5. If an issue says a value is wrong — correct it to match the source document exactly.
```

---

## Step 3 — `prompts/ocr_executor/user.md`

### Edit 3a: Move critic_feedback section before document_content

The current file content is:

```
<execution_context>
user_request: |
  {{USER_REQUEST}}

active_schema: {{ACTIVE_SCHEMA}}

step:
  title: {{STEP_TITLE}}
  input: {{STEP_INPUT}}
  output: {{STEP_OUTPUT}}
  success_criteria: |
    {{STEP_SUCCESS_CRITERIA}}

document_content: |
  {{DOCUMENT_CONTENT}}

previous_results: |
  {{PREVIOUS_RESULTS}}

critic_feedback: |
  {{CRITIC_FEEDBACK}}
</execution_context>

Task: Extract medical data from the document_content above and respond with a valid JSON object conforming to the MedicalDoc schema. Use the step definitions and previous_results to understand context. Address any issues listed in critic_feedback.
```

Replace the ENTIRE file content with:

```
<execution_context>
user_request: |
  {{USER_REQUEST}}

active_schema: {{ACTIVE_SCHEMA}}

step:
  title: {{STEP_TITLE}}
  input: {{STEP_INPUT}}
  output: {{STEP_OUTPUT}}
  success_criteria: |
    {{STEP_SUCCESS_CRITERIA}}

critic_feedback: |
  {{CRITIC_FEEDBACK}}

document_content: |
  {{DOCUMENT_CONTENT}}

previous_results: |
  {{PREVIOUS_RESULTS}}
</execution_context>

Task: Extract medical data from the document_content above and respond with a valid JSON object conforming to the MedicalDoc schema. Use the step definitions and previous_results to understand context. Address ALL issues listed in critic_feedback.
```

---

## Step 4 — `flows/pec/orchestrator.py`

### Edit 4a: Add max_retries parameter to __init__

Find EXACTLY:

```python
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
```

Replace with:

```python
    def __init__(
        self,
        *,
        planner: Planner,
        executor: OcrExecutor,
        critic: Critic,
        max_retries: int = 2,
    ):
        self._planner = planner
        self._executor = executor
        self._critic = critic
        self._max_retries = max_retries
```

### Edit 4b: Replace single execute+critic call with retry loop in run()

Find EXACTLY:

```python
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
```

Replace with:

```python
        retry_count = 0
        for attempt in range(self._max_retries + 1):
            await self.execute(runCtx)
            await self.critic(runCtx)

            if runCtx.status == RunStatus.COMPLETED:
                break

            if attempt < self._max_retries:
                retry_count += 1
                log.info(
                    "Critic rejected (attempt %d/%d), retrying",
                    attempt + 1,
                    self._max_retries,
                )
                runCtx.doc = None

        return OcrResult(
            document_path=file_path,
            schema_name=runCtx.active_schema,
            context=runCtx.doc.model_dump_json() if runCtx.doc else "",
            step_results=runCtx.steps_results,
            retry_count=retry_count,
            status=runCtx.status,
        )
```

---

## Step 5 — `flows/pec/build_pec.py`

### Edit 5a: Pass max_retries from app config to Orchestrator

Find EXACTLY:

```python
    return Orchestrator(
        planner=planner,
        executor=executor,
        critic=critic,
    )
```

Replace with:

```python
    return Orchestrator(
        planner=planner,
        executor=executor,
        critic=critic,
        max_retries=app_cfg.orchestrator.max_retries,
    )
```

---

## Verification sequence

Run these commands in order after all edits are done:

```bash
# 1. Syntax check
uv run python -c "from flows.pec.orchestrator import Orchestrator; print('OK')"
uv run python -c "from flows.pec.build_pec import build_pec; print('OK')"

# 2. Unit tests
uv run pytest

# 3. Run planner on a test document to verify single-step output
uv run advisor plan docs/medocs/orig/2015-11-16_emergency-kidney-colic.json

# 4. Run executor on the plan output to verify clean result
uv run advisor exec docs/medocs/plans/2015-11-16_emergency-kidney-colic.yaml
```

Expected in plan output: `steps` array has exactly 1 item.
Expected in exec output: `steps_results` has 1–3 items, `doc` has no duplicate findings/recommendations.

---

## What does NOT change

- `config/{dev,prod,test}/app.yaml` — already have `orchestrator.max_retries`
- `flows/pec/models.py` — `notes` field already `list[str]` with working validator; corruption from multi-step merge will not occur with single-step extraction
- `flows/pec/planner.py` — logic unchanged
- `flows/pec/ocr_executor.py` — logic unchanged
- `flows/pec/critic.py` — logic unchanged
- `flows/pec/renderer.py` — unchanged
- `prompts/critic/system.md` — unchanged
- `flows/pec/models.py:MedicalDoc.merge()` — keep as-is (used by CLI debug commands)

---

## Phase 2 (future — not in this task)

Iterative refinement when single-step is not enough for complex documents:

1. `CriticResult` gets `refinement_request: str | None`
2. Critic system prompt: formulate `refinement_request` with specific missing fields and where to find them
3. `Orchestrator.refine(runCtx)`: calls Planner with critic feedback, gets targeted plan, executes patch steps
4. `PatchResult` model: partial MedicalDoc with explicit "only these fields changed" semantics
5. Deterministic Python merge: patch + existing_doc → updated_doc
6. Critic validates final doc
