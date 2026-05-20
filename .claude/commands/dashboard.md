---
description: Abre el dashboard de Phoenix y resume el estado actual del sistema
---

Open the Phoenix dashboard and produce a textual summary of the system state.

Execute these steps:

1. Verify Phoenix is running at `http://localhost:6006`. If not, surface the error.
2. Print the dashboard URL so the user can open it in the browser.
3. Query the Phoenix API (or its backing store) to summarize the last 24h:
   - Total queries processed.
   - p50, p95 latency per phase (rewrite, retrieve, rerank, generate, total TTFT).
   - Average tokens cached vs fresh (context caching impact).
   - Estimated total token consumption.
   - Number of incidents flagged by each security layer.
   - Top 5 most active users (by user_id).
4. Render the summary as a Markdown table.
5. If any phase shows latency above its threshold, highlight it and propose investigation.

Do not modify Phoenix data. This command is read-only.
