  Analyze this document and create an extraction plan.

   ## User Request

   {{USER_REQUEST}}

   ## Document Content

   {{DOCUMENT_CONTENT}}

   ## Instructions

   1. Determine if this is a medical document
   2. If yes → select the best schema from the catalog (in system prompt) and create extraction steps
   3. If no → return action "SKIP" with explanation in goal

   Respond with valid JSON.