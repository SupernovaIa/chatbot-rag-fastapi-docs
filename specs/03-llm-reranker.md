# Spec 03 · LLM-as-reranker (RankGPT)

**Estado:** aceptada
**Bloque:** R (Retrieval modular)
**Dependencias:** Spec 02 (hybrid search), ADR-004 (LLM-reranker vs cross-encoder)

## Goal

Reordenar los top-K candidatos del retrieval híbrido con Gemini Flash, devolviendo los más relevantes para la query.

## User story

> Como pipeline RAG, quiero pasar los 20 candidatos del retrieval híbrido a un LLM que los puntúe contra la query y me devuelva los 5 mejores reordenados.

## Approach

- [ ] Prompt del reranker en `prompts/reranker.md`, versionado.
- [ ] Entrada al LLM: query + lista numerada de candidatos con `id` y `content` truncado.
- [ ] Salida esperada: JSON con array de ids en orden de relevancia descendente.
- [ ] Parser robusto: si el LLM no devuelve JSON válido, fallback al orden original con log de warning.
- [ ] Timeout: si el rerank tarda > 5s, devolver orden original.
- [ ] Top-K de salida configurable (default 5).

## Acceptance criteria

- `rerank(query: str, candidates: list[Chunk], top_k: int) -> list[Chunk]`.
- Test con mocking de Gemini que devuelve JSON válido: chunks reordenados.
- Test con mocking de Gemini que devuelve basura: fallback al orden original sin crash.
- Latencia p50 < 2s para 20 candidatos.
- Trazas Phoenix muestran fase `rerank` con `input_count`, `output_count`, `latency_ms`, `fallback_used`.

## Riesgos

- LLM puede devolver ids inventados. El parser debe descartarlos.
- Coste en queries con rate limit alto. Free tier puede saturar bajo carga.

## Preguntas abiertas

- ¿Pasar contenido completo del chunk o resumen? Default contenido completo truncado a 500 chars.
- ¿Listwise vs pointwise rerank? Default listwise (un solo prompt con todos).
