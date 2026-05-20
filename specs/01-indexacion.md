# Spec 01 · Indexación del corpus

**Estado:** aceptada
**Bloque:** B (Corpus + Indexación)
**Dependencias:** ADR-002 (pgvector), ADR-003 (Azurite Blob)

## Goal

Tener el corpus de FastAPI docs indexado en pgvector, consultable y reproducible bajo un SHA del corpus.

## User story

> Como operador del sistema, quiero ejecutar `python scripts/index_corpus.py` y obtener el corpus completo indexado en pgvector con metadatos y embeddings, leyéndolo desde Azurite como si fuera Azure Blob real.

## Approach

- [ ] Snapshot del corpus pinned a SHA en `corpus/sample/fastapi-docs/`.
- [ ] `scripts/upload_corpus.py` lee los `.md` y los sube a Azurite (container `corpus`).
- [ ] `backend/app/indexing/loader.py` lista blobs y descarga en streaming.
- [ ] Splitter Markdown-aware con fallback a recursivo: 512 tokens, solape 80.
- [ ] Embeddings con `gemini-embedding-001` fijando `output_dimensionality=1536` (el modelo es 3072 por defecto; 1536 es uno de los tamaños MRL recomendados). Re-normalizar (L2) el vector tras truncar: solo el 3072 viene normalizado.
- [ ] Embeddings en batch con `tenacity` para backoff exponencial.
- [ ] Schema pgvector: `chunks(id, content, embedding vector(1536), metadata jsonb, content_tsv tsvector, corpus_sha, indexed_at)`.
- [ ] Índices HNSW (vector_cosine_ops) y GIN (content_tsv).
- [ ] Idempotencia: hash del contenido + SHA del corpus como clave única.

## Acceptance criteria

- `docker compose exec backend python scripts/index_corpus.py` completa sin errores.
- Tabla `chunks` tiene N filas correspondientes al corpus completo.
- Cada chunk tiene `embedding` no nulo y `metadata` con `source`, `section`, `corpus_sha`.
- Tests unitarios pasan con mocking de Gemini.
- Re-ejecución de indexación no duplica filas.

## Riesgos

- Rate limit de Gemini en indexación masiva → mitigar con backoff y batch.
- Cambio del SHA del corpus rompe el dataset gold → script de validación en bloque G.

## Preguntas abiertas

- Tamaño de batch óptimo (50 vs 100 textos por llamada): validar en bloque B.
- Estrategia de re-embedding si Google cambia el modelo: documentar en ADR.
