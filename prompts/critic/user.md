<review_context>
user_request: |
{{USER_REQUEST}}

active_schema: {{ACTIVE_SCHEMA}}

success_criteria: |
{{SUCCESS_CRITERIA}}

document_content: |
{{DOCUMENT_CONTENT}}

final_doc: |
{{FINAL_DOC}}
</review_context>

Task: Review the final_doc against the document_content and success_criteria. Return a JSON verdict with approved (bool), summary (string), and issues (array of severity/description/suggestion objects).
