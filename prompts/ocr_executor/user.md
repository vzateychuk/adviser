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

Task: Extract medical data from the document_content above and respond with a valid JSON object conforming to the MedicalDoc schema. Use the step definitions to understand your task. The previous_results field shows the result of a previous attempt that was rejected; use it only to avoid repeating the same mistakes, not as a source of truth. Address ALL issues listed in critic_feedback.
