# Spec 02 · Búsqueda híbrida con RRF

**Estado:** aceptada
**Bloque:** R (Retrieval modular)
**Dependencias:** Spec 01 (indexación con HNSW + GIN)

## Goal

Implementar búsqueda híbrida densa + léxica con Reciprocal Rank Fusion en una sola query SQL contra pgvector.

## User story

> Como pipeline RAG, quiero recibir una query, lanzar simultáneamente búsqueda vectorial (coseno) y búsqueda léxica (`tsvector`) y combinar resultados por RRF para devolver los top-K más relevantes.

## Approach

- [ ] Embedding de la query con `gemini-embedding-001` (mismo modelo que el corpus).
- [ ] Query SQL con CTEs: `dense_results`, `sparse_results`, `combined`.
- [ ] RRF: `score = 1/(k + rank_dense) + 1/(k + rank_sparse)`, k=60 default.
- [ ] Parametrizable: top-K candidatos (default 20), pesos (default iguales).
- [ ] Filtros opcionales por metadata (preparados pero no usados en v1).

## Acceptance criteria

- `retrieve_hybrid(query: str, top_k: int) -> list[Chunk]` retorna chunks ordenados.
- Test unitario: query con término exacto recupera chunk relevante en top-3.
- Test unitario: query con paráfrasis recupera chunk relevante en top-5.
- Latencia local p50 < 100ms para top-K=20.
- Trazas en Phoenix muestran fase `hybrid_search` con `dense_results_count`, `sparse_results_count`, `combined_top_k`.

## Riesgos

- pgvector con poco data puede dar resultados no calibrados. Mitigar evaluando contra dataset gold completo.
- RRF k=60 puede no ser óptimo para este corpus. A medir.

## Preguntas abiertas

- ¿Usamos `<=>` (coseno) o `<->` (L2) para distancia? Default coseno por consistencia con docs de embeddings.
