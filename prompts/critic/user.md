<review_context>
user_request: |
    {{USER_REQUEST}}

active_schema: {{ACTIVE_SCHEMA}}

step: |
    {{STEP}}

success_criteria: |
    {{SUCCESS_CRITERIA}}

document_content: |
    {{DOCUMENT_CONTENT}}

step_result: |
    {{STEP_RESULT}}
</review_context>

## Instructions

Verify that the extraction in step **{{STEP.title}}** satisfies the listed success criteria. If any criteria are not met, raise an issue. If all criteria are met and there are no manufacturing defects, return an empty result (no issues).