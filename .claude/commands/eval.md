---
description: Ejecuta el dataset gold completo contra el pipeline y muestra métricas
---

Run the full gold dataset evaluation against the current pipeline and report metrics.

Execute these steps:

1. Verify the gold dataset exists at `corpus/sample/fastapi-docs/evals/gold.jsonl` and has the expected count (40 examples).
2. Verify pgvector is populated with the indexed corpus. If not, suggest running `/index` first.
3. Execute `docker compose exec backend pytest tests/evals -v` (runs the full suite: single-turn and multi-turn, all 40 examples).
4. Stream the output so the user sees progress per example.
5. After completion, present the metrics table:
   - faithfulness
   - answer_relevancy
   - context_precision
   - context_recall
   - recall@5
   - MRR
6. Compare each metric to the thresholds defined in `backend/tests/evals/thresholds.yaml`.
7. Highlight which metrics pass and which fail. Mark FAIL in red equivalent (use bold).
8. If any metric fails: list the example IDs that failed and the actual vs expected for each.
9. Show the Phoenix trace URL for the run if available.

Do not silently skip examples. If parsing of an example fails, surface it explicitly.
