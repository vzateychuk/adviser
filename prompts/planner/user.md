  Analyze this document and create an extraction plan.

   ## User Request

   {{USER_REQUEST}}

   ## Document Content

   {{DOCUMENT_CONTENT}}

   ## Available Schemas

   {{SCHEMA_CATALOG}}

   ## Instructions

   1. Determine if this is a medical document
   2. If yes → select the best schema from the catalog and create extraction steps
   3. If no → return action "SKIP" with explanation in goal

   Respond with valid JSON.