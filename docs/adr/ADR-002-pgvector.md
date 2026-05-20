# ADR-002: Postgres + pgvector como vector store

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** vector-store, infrastructure

## Contexto

Necesitamos un vector store para 1536-dim embeddings con búsqueda vectorial e híbrida. Debe correr en local sin tarjeta, ser idéntico (o casi) al managed que el alumno usará después.

## Drivers

- Cero tarjeta en local.
- Hybrid search nativo (vector + BM25).
- Misma tecnología en local y en cloud gestionado (Azure DB for PostgreSQL, Supabase, RDS).
- SQL conocido, no aprender una DSL nueva.

## Opciones consideradas

- A. Postgres + pgvector.
- B. Qdrant self-hosted.
- C. Chroma local.
- D. Pinecone (managed, requiere cuenta).

## Decisión

Opción A. Postgres 17 con pgvector 0.8+ en Docker. Hybrid search con `tsvector`. Índice HNSW para denso, GIN para léxico.

La versión exacta de pgvector la trae la imagen Docker (`pgvector/pgvector:pg17`); anclar el tag vigente al construir. 0.8.2 es la referencia estable confirmada; usar la más reciente disponible en la imagen.

## Consecuencias

### Positivas

- SQL estándar. El alumno reutiliza conocimiento.
- Postgres único para vector store, historial, usuarios, auth. Menos infra.
- Migración a Azure DB for PostgreSQL es cambio de connection string.

### Negativas

- A muy alta escala (>50M vectores, >500 QPS), pgvector empieza a sufrir. Fuera del scope didáctico.

## Alternativas descartadas

- Qdrant: mejor performance pero infra adicional.
- Chroma: insuficiente para hybrid search nativo en v1.0.
- Pinecone: requiere cuenta, fuera del scope cero tarjeta.
