---
description: Reindexa el corpus completo desde Azurite a pgvector
---

Reindex the entire corpus from Azurite into pgvector.

Run these steps:

1. Verify Azurite is reachable at `http://azurite:10000` (or the configured endpoint).
2. Verify the Postgres container is healthy and pgvector is installed.
3. Execute `docker compose exec backend python scripts/index_corpus.py` and stream the output.
4. After completion, run a sanity query against pgvector to confirm row count matches the expected number of chunks.
5. Report:
   - Number of files indexed.
   - Number of chunks created.
   - Total embedding tokens consumed.
   - Total elapsed time.
   - Any rate limit retries triggered.

If the indexing fails, do not silently continue. Stop, surface the error, and propose remediation.
