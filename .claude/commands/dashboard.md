---
description: Abre el dashboard de Phoenix y resume el estado actual del sistema
---

Open the Phoenix dashboard and produce a textual summary of the system state.

## Steps

1. **Verify Phoenix** is running at `http://localhost:6006`. Use:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://localhost:6006/healthz
   ```
   If it returns anything other than `200`, report: "Phoenix is not running. Start the stack with `docker compose up -d`." and stop.

2. **Print the dashboard URL** so the user can open it in the browser:
   - Main trace view: http://localhost:6006/
   - Spans API: http://localhost:6006/v1/spans

3. **Query the Phoenix spans API** for the last 24 hours using the project `chatbot-rag-fastapi-docs`. Execute a curl like:
   ```bash
   curl -s "http://localhost:6006/v1/spans?project_name=chatbot-rag-fastapi-docs&limit=500" | python3 -c "
   import sys, json, statistics
   data = json.load(sys.stdin)
   spans = data.get('data', [])
   print(json.dumps({'count': len(spans), 'names': list({s.get('name','') for s in spans})}, indent=2))
   "
   ```
   If the API returns an error, try the alternative: `http://localhost:6006/api/v1/spans`.

4. **Compute the following metrics** from the spans (parse the JSON response):

   ### Health metrics (span `chat_turn`)
   - Total chat turns in the last 24h
   - p50, p95 of `total_latency_ms`
   - Error rate (spans with status = ERROR)

   ### Per-phase latency (from child spans)
   - `rewrite`: p50, p95 of span duration
   - `hybrid_search`: p50, p95 of span duration
   - `rerank`: p50, p95 of `latency_ms`; rate of `fallback_used = true`
   - `generate`: p50, p95 of `ttft_ms`; mean `prompt_tokens`, `cached_tokens`, `output_tokens`

   ### Cost / caching (span `generate`)
   - Mean `cost_usd` per turn
   - Total `cost_usd` in the window
   - Mean `cache_hit_rate`
   - Turns with `caching_available = true` (rate)
   - Total `savings_usd`

   ### Evals quality (span `evals.run`)
   - Last run: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`
   - Subset, corpus SHA, commit SHA
   - Whether any metric is below its floor (see `docs/cost-model.md` for floors)

5. **Render the summary** as a Markdown table with three sections (Health, Consumption, Quality). Use emojis to highlight status:
   - ✅ within threshold
   - ⚠️ approaching threshold (> 80 % of limit)
   - ❌ above threshold / below floor

6. **Highlight slow phases**: if any phase p95 exceeds its alert threshold (from `infra/phoenix/dashboards/health.json`), print an investigation hint:
   - `rerank` p95 > 12 000 ms → "Reranker approaching timeout. Check free-tier quota or reduce candidates."
   - `generate` ttft p95 > 5 000 ms → "High TTFT. Check Gemini API latency or system prompt length."
   - `chat_turn` p95 > 30 000 ms → "End-to-end latency is high. Investigate reranker and/or generation."

7. **Point to dashboard definition files**:
   - Health: `infra/phoenix/dashboards/health.json`
   - Quality: `infra/phoenix/dashboards/quality.json`
   - Cost: `infra/phoenix/dashboards/cost.json`

Do not modify Phoenix data. This command is read-only.

## Fallback when Phoenix is unreachable

If Phoenix is running but the spans API returns no data (e.g., no turns have been sent yet):
- Print: "Phoenix is running but no spans found in the last 24h. Send a chat message first."
- Still print the dashboard URLs and the definition file locations.

## Dashboard definition files

The JSON files in `infra/phoenix/dashboards/` define the panels, queries and alert thresholds for the 3 dashboards. They are used by this command to compute the summary and can be used to manually recreate dashboards in the Phoenix UI.
