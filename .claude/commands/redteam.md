---
description: Ejecuta la checklist de red teaming contra el chatbot
---

Run the red team checklist against the chatbot to verify defenses in depth.

Execute these steps:

1. Load `security/red-team-checklist.md`. Each entry contains a hostile prompt, the expected blocking layer (1 to 5) and the expected outcome.
2. For each entry, send the prompt to the `/chat` endpoint (authenticated with a test user).
3. Capture:
   - Which defense layer blocked or processed the request (from Phoenix trace).
   - The actual response returned to the user.
   - Whether sensitive information leaked (compare against expected outcome).
4. Build a results table:
   - Prompt ID
   - Expected layer
   - Actual layer
   - Expected outcome
   - Actual outcome
   - PASS / FAIL
5. Summarize:
   - Total tested
   - Passed
   - Failed (list IDs)
6. For each failed entry, propose remediation: tighter prompt in the appropriate layer, additional regex rule, etc.

Do not commit any changes from this command. The purpose is inspection and reporting.
