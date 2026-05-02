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

Task: Extract medical data from the document_content above and respond with a valid JSON object conforming to the MedicalDoc schema.
Use the step definitions to understand your task. 
Do NOT copy values from previous_results — extract everything fresh from document_content. 
Use previous_results only to understand what went wrong in the prior attempt. 
Address ALL issues listed in critic_feedback.
