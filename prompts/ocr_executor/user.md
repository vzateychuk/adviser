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
