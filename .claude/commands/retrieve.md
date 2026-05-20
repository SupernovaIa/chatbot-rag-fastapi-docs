---
description: Ejecuta una query de retrieval manual para inspección y debugging
---

Run a manual retrieval query against the indexed corpus to inspect what the pipeline returns.

The user provides the query as an argument. If no query is provided, ask for one before proceeding.

Execute these steps:

1. Embed the query with `gemini-embedding-001`.
2. Run hybrid search (dense + BM25 with RRF) on pgvector. Show top-20 candidates with scores.
3. Run LLM-as-reranker (Gemini Flash) over the top-20. Show the reranked top-5.
4. Print, for each of the top-5:
   - Source path and section.
   - First 200 chars of content.
   - Dense rank, sparse rank, RRF score, rerank position.
5. Do NOT call the generator. This command is for retrieval inspection only.
6. Show the Phoenix trace URL for this run if observability is configured.

If pgvector is empty or unreachable, surface the error and suggest running `/index` first.
