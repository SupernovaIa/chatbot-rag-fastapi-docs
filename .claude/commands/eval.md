---
description: Ejecuta el dataset gold completo contra el pipeline y muestra métricas
---

Run the gold dataset evaluation against the current pipeline and report metrics
through the eval runner (`backend/app/evals/`, spec 10 / ADR-007).

Execute these steps:

1. Verify the gold dataset exists at `corpus/sample/fastapi-docs/evals/gold.jsonl` and has 40 examples.
2. Verify pgvector is populated with the indexed corpus. If not, suggest running `/index` first.
3. Confirm `GOOGLE_API_KEY` is set (the RAGAS judge is Gemini Pro; use `--no-judge` for a deterministic dry run that skips RAGAS).
4. Run the runner inside the backend container:
   - Full suite (40 examples, judge included):
     `docker compose exec backend python -m app.evals.cli --subset full`
   - PR subset (representative ~15 examples, free-tier friendly):
     `docker compose exec backend python -m app.evals.cli --subset ci_subset`
   - To compare against the recorded main baseline, append `--baseline baseline_metrics.json`.
5. Stream the output so the user sees the Markdown report as it prints.
6. The runner already prints the metrics table:
   - faithfulness, answer_relevancy, context_precision, context_recall (RAGAS, Gemini Pro)
   - recall@5, MRR (deterministic, over answerable examples)
   - abstention_rate (advisory, over `no_se` examples)
7. The table marks PASS/FAIL per metric against `backend/app/evals/thresholds.yaml`
   (absolute floor + optional relative regression vs the main baseline).
8. If the gate fails (exit code 1): list the failing metrics with their reason
   and the example IDs that errored, if any.
9. Each run emits a Phoenix `evals.run` span (metrics, timestamp, commit SHA) for
   the Quality dashboard — show the Phoenix URL (`http://localhost:6006`) if available.

Do not silently skip examples. A per-example failure is captured on the run and
surfaced in the report; relay it explicitly.
