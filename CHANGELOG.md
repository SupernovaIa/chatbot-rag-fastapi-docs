# Changelog

Todos los cambios notables de este proyecto se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado según [SemVer](https://semver.org/lang/es/).

## [No publicado]

Próximas entradas por bloque.

---

## [Bloque CH] — 2026-05-21

### Añadido
- `backend/migrations/versions/0002_create_chat_tables.py` — tablas `chat_sessions` (id UUID PK, user_id UUID nullable hasta bloque AU, timestamps) y `chat_messages` (turn_idx, role `user|assistant`, content, citations JSONB). Índice de soporte `(session_id, turn_idx)` + constraint UNIQUE `(session_id, turn_idx, role)` (specs 05/06).
- `prompts/system.md` — system prompt versionado con front-matter YAML. ~1 200 tokens (>mínimo Flash ~1 024 para caching implícito). Contiene: rol y alcance, principios, formato de respuesta, formato de citas con ejemplo completo, comportamiento multi-turn, «no sé» cases, tono (spec 07).
- `backend/app/chat/models.py` — dataclasses de dominio: `ChatSession`, `ChatMessage`, `ChatTurn`, `Citation`, `UsageMeta` (con `from_response_metadata` que extrae `cached_content_token_count`), `StreamEvent`.
- `backend/app/chat/store.py` — `ChatHistoryStore`: CRUD de sesiones y mensajes, `load_history` con sliding window N=5 (ADR-005), `save_turn` transaccional con ON CONFLICT DO NOTHING, `next_turn_idx` (spec 06).
- `backend/app/chat/prompts.py` — `build_prompt` (SystemMessage estable + HumanMessage dinámico), `build_context_block`, `build_history_block`, `citations_from_candidates`, `system_prompt_hash` para tracing (spec 07).
- `backend/app/chat/generator.py` — `StreamingSession` (contenedor mutable de estado post-stream); `stream_chat` async generator que emite eventos `token`/`error`, captura `UsageMeta` del último chunk de LangChain (spec 05). Cancelación limpia vía `asyncio.Event` (spec 05: evitar malgasto de free tier).
- `backend/app/chat/router.py` — `POST /chat/`: pipeline completo (load history → `asyncio.to_thread(retrieve)` → `build_prompt` → `stream_chat` → persist); disconnect watcher con `asyncio.create_task`; `logger.debug` de usage/session post-stream (TODO: span OTel manual en bloque F). `GET /chat/sessions`, `GET /chat/sessions/{id}` (sin auth hasta bloque AU) (specs 05/06).
- `backend/tests/chat/` — 46 tests nuevos: `test_store.py` (8), `test_prompts.py` (11), `test_generator.py` (9), `test_router.py` (12 chat + 3 GET); fakes en memoria, LLM mockeado con `patch`. 135 tests totales, todos verdes.

### Cambiado
- `backend/app/config.py` — añadidos `generate_timeout_s = 60.0` y `history_window_n = 5`.
- `backend/app/main.py` — incluye `chat_router` (prefijo `/chat`).
- `backend/pyproject.toml` + `uv.lock` — dep `sse-starlette>=2.1` (instalada 3.4.4).
- `backend/app/chat/__init__.py` — docstring de módulo.
- `docker-compose.yml` — bind mount `./prompts:/prompts:ro` en el servicio backend (los prompts están en la raíz del repo, fuera del build context `./backend`; el path resuelto en el contenedor es `/prompts/`).
- `specs/06-history-management.md` — corrección: constraint UNIQUE `(session_id, turn_idx, role)`, no `(session_id, turn_idx)`. Explicación añadida.

### Decisiones documentadas
- **UNIQUE (session_id, turn_idx, role)** en lugar de `(session_id, turn_idx)`: la spec describía la segunda, pero user y assistant comparten `turn_idx` → constraint incorrecto en producción. Documentado en la migración y corregido en la spec.
- **Sin `CachedContent` explícito** (spec 07): mínimo documentado para *implicit* caching en Gemini Flash es **1 024 tokens** (ai.google.dev/gemini-api/docs/caching); nuestro system prompt tiene ~1 107 tokens reales → por encima del umbral. Se apostó por caching implícito automático (sin gestión de `cache_id`/TTL). Nota: el mínimo para *explicit* caching (`CachedContent`) es 32 768 tokens — no aplica aquí.
- **`build_prompt` de dos mensajes**: SystemMessage (prefijo estable, igual entre todas las queries) + HumanMessage (contenido dinámico). Historial embebido en el HumanMessage para no romper la estabilidad del primer mensaje.
- **`asyncio.to_thread`** para retrieval síncrono y DB síncrona desde un router async; evita bloquear el event loop en llamadas de red al embedding y a Postgres.
- **`ChatGoogleGenerativeAI` importado a nivel de módulo** en `generator.py` (no dentro de la función) para que `patch("app.chat.generator.ChatGoogleGenerativeAI")` funcione en los tests.

### Notas
- **Verificación live (2026-05-21):** stream de 2 turnos verificado con `curl -N` contra stack Docker real. Turno 1 y turno 2 con mismo `session_id` → tokens + evento `citations` en ambos. 19 spans en Phoenix (2× retrieval pipeline completo + 2× LLM ChatGoogleGenerativeAI).
- **Hallazgo caching implícito (precisado 2026-05-21):** valor exacto `None` (no `0`) en turno 1 y turno 2. Mínimo oficial para Gemini Flash: **1 024 tokens** (fuente: ai.google.dev/gemini-api/docs/caching, verificado con Context7). Prefijo medido con SDK directo: 1 107–1 302 tokens en 4 llamadas → **por encima del mínimo**. Caso: "prefijo > mínimo y aun así `None`". Causa LangChain confirmada: `astream()` no expone `usage_metadata` en `response_metadata` de streaming. Hipótesis sobre causa raíz: (1) model ID `gemini-3.5-flash` puede no coincidir con los modelos listados en la doc ("Gemini 3 Flash Preview"/"Gemini 2.5 Flash"); (2) free tier puede no incluir implicit caching. Issue de follow-up: **#12**.
- **Bug OTel span generador** (diferido a bloque F): `set_span_attributes` dentro de `event_generator()` es no-op porque el route handler retorna la `EventSourceResponse` antes de que el generador complete; no hay span activo. Solución: `tracer.start_span()` manual pasado al generador. Actualmente los datos de usage se loguean con `logger.debug`.
- Auth (`POST /chat` debería requerir JWT cookie) diferida a bloque AU.
- `curl -N http://localhost:8000/chat/ -d '{"query":"..."}' -H 'Content-Type: application/json'` funciona contra el stack Docker.

---

## [Bloque R] — 2026-05-21

### Añadido
- `backend/app/retrieval/`: módulo de retrieval modular (package-by-feature, ADR-011).
  - `hybrid.py`: `PgVectorHybridSearcher` — búsqueda híbrida densa (coseno `<=>`) + léxica (`ts_rank_cd` sobre `content_tsv`) fusionada con Reciprocal Rank Fusion (k=60) en una **única query SQL** con CTEs y FULL OUTER JOIN (spec 02).
  - `reranker.py`: LLM-as-reranker RankGPT listwise con Gemini Flash (ADR-004); parser tolerante (descarta ids inventados, reañade omitidos) y fallback robusto al orden híbrido ante JSON inválido / timeout / error (spec 03).
  - `rewriter.py`: query rewriting multi-turn con sliding window N=5 (ADR-005); devuelve la query original si no hay historial o el LLM falla (spec 04).
  - `orchestrator.py`: `retrieve()` — rewrite → embed → hybrid → rerank.
  - `llm.py`: `GeminiChatAdapter` (Gemini Flash vía LangChain `ChatGoogleGenerativeAI`) y `QueryEmbeddingsAdapter` (`RETRIEVAL_QUERY`). `_extract_text` aplana el `content` en bloques de los modelos *thinking* de Gemini 3.x.
  - `ports.py`, `models.py`, `prompts.py`, `router.py`.
- `backend/app/observability/tracing.py`: setup OpenTelemetry → Phoenix con OpenInference para LangChain y helper `@traced` + `set_span_attributes` (ADR-008). Defensivo: no-op si Phoenix/libs no disponibles, gateado por `DISABLE_TRACING`.
- `POST /retrieve`: endpoint que devuelve el top-5 reranqueado con scores (`rrf_score`, dense/sparse rank, `rerank_position`); no llama al generador.
- `prompts/reranker.md`, `prompts/rewriter.md`: prompts versionados (metadata + placeholders `{{var}}`).
- `scripts/manual_retrieval_check.py`: calcula recall@5 / MRR / hit-rate sobre el gold (híbrido o pipeline completo).
- Tests: `backend/tests/retrieval/` (26 tests con Gemini y DB mockeados) + `backend/tests/conftest.py` (desactiva tracing en tests).
- Dependencias: `arize-phoenix-otel`, `openinference-instrumentation-langchain`, `opentelemetry-exporter-otlp`.

### Cambiado
- `backend/app/main.py`: inicializa tracing al arranque e incluye el router de retrieval.
- **Timeout del reranker/rewriter (fix de review):** se aplica en el cliente (`GeminiChatAdapter(timeout=…)`), no como `config` de `.invoke()` (que `RunnableConfig` ignora). Clientes dedicados para rewrite y rerank con sus timeouts (spec 03: > 5 s → orden híbrido vía fallback). Log de query original/reescrita bajado a DEBUG (PII, CLAUDE.md).
- `backend/app/config.py`: añadidos `gemini_flash_model` (anclado `gemini-3.5-flash`), `corpus_sha` y parámetros de retrieval (candidatos 20, top_k 5, rrf_k 60, timeouts de rerank/rewrite).

### Decisiones documentadas
- **Model ID Flash anclado `gemini-3.5-flash`** (verificado vía `models.list()` de Google AI Studio el 2026-05-21; coincide con el default de ADR-001).
- **Bug Gemini 3.x *thinking***: `ChatGoogleGenerativeAI` devuelve `content` como lista de bloques; sin aplanar daba cadena vacía y el reranker caía siempre en fallback (rerank ≡ híbrido). Corregido con `_extract_text` + test.
- recall@5 medido sobre los 30 single-turn con `gold_chunks`; los 5 `no_se` (sin gold) se excluyen del recall por diseño y se reportan aparte.

### Notas
- **Baseline de retrieval** (corpus_sha `40e33e4`, 30 single-turn): recall@5 0.750 (híbrido) → **0.867** (con reranker); hit-rate 0.833 → 0.900; MRR 0.629 → **0.801**. Gate (recall@5 > 0.7) superado.
- **Tracing verificado en el dashboard de Phoenix**: traza única con span por fase (rewrite/hybrid_search/rerank/retrieve) + span LLM auto-instrumentado.
- **Deuda — BM25 cross-lingual**: queries en español vs corpus en inglés → la pierna léxica aporta poco (no comparten léxico salvo identificadores de código/API); el puente lo da el embedding denso multilingüe. No es problema de config del `tsvector` (los docs inglés deben seguir en `english`). A evaluar en iteración futura, probablemente con ADR corto.

---

## [Bloque G] — 2026-05-21

### Añadido
- `corpus/sample/fastapi-docs/evals/`: directorio del dataset gold de evaluación (spec 08).
- `corpus/sample/fastapi-docs/evals/README.md`: schema documentado del dataset (campos, `gold_chunks`, ejemplos «no sé», distribución, validación).
- `corpus/sample/fastapi-docs/evals/gold.jsonl`: 40 ejemplos en español, **revisados y firmados a mano** (`reviewed_by: javi`, `reviewed_at: 2026-05-21`). Distribución: 15 factual, 8 paráfrasis, 7 multi-fuente, 5 «no sé», 5 multi-turno.
- `scripts/validate_gold.py`: validador del dataset — parseo JSONL, schema, distribución, firma obligatoria y existencia de cada `gold_chunk` en pgvector con el `corpus_sha` actual.
- `backend/tests/test_validate_gold.py`: 16 tests del validador (schema, distribución, firma, smoke contra `gold.jsonl` real). Todos verdes.

### Decisiones documentadas
- Spec 08 implementada. `gold_chunks` referencia el par `{source, section}` de los metadatos de `chunks` en pgvector; el validador exige que exista al menos un chunk por par con el SHA vigente.
- Revisión humana obligatoria: el agente propone borradores, Javi revisa, ajusta y firma. Ningún ejemplo se acepta sin firma (lo hace cumplir el validador y el test).
- Ajuste en revisión: g-02 pasó a dos `gold_chunks` (se añadió «Path Parameters > Data validation») para fundamentar la afirmación del error HTTP 422.
- `REVIEW.md` (andamiaje de la revisión humana) queda fuera del control de versiones: ignorado vía `corpus/**/evals/REVIEW.md`. El deliverable es `gold.jsonl` firmado + `validate_gold.py` + tests + README de schema.

### Deuda técnica conocida
- **Cobertura del corpus concentrada:** los 40 ejemplos se apoyan en ~15 de los 144 ficheros del corpus, sesgados al tutorial básico (path/query params, body, errores, CORS, async, CLI, entornos virtuales). Falta cubrir `advanced/`, `how-to/`, seguridad/OAuth2, dependencias, SQL, etc.
- **Multi-fuente multi-sección:** g-27 y g-30 combinan varias secciones del mismo fichero (válido según la spec 08, que define multi-fuente por nº de `gold_chunks`, no por documentos distintos), no documentos distintos.
- Ampliar cobertura y diversidad de fuentes en una iteración futura.

---

## [Bloque B] — 2026-05-21

### Añadido
- `corpus/sample/fastapi-docs/`: 144 ficheros `.md` de la documentación oficial de FastAPI v0.115.0 (tag), pinneados al commit SHA `40e33e492dbf4af6172997f4e3238a32e56cbe26`.
- `corpus/sample/fastapi-docs/SOURCE.md`: origen, SHA, licencia e instrucciones de reproducción del snapshot.
- `scripts/upload_corpus.py`: sube los `.md` al container `corpus` de Azurite; idempotente (overwrite).
- `scripts/index_corpus.py`: pipeline completo de indexación; idempotente via `chunk_hash`.
- `backend/app/indexing/models.py`: `BlobItem`, `Chunk` con `chunk_hash` SHA-256 auto-calculado.
- `backend/app/indexing/ports.py`: puertos `BlobLoaderPort`, `EmbeddingsPort`, `ChunkStorePort` (Protocol, ADR-011).
- `backend/app/indexing/loader.py`: `AzuriteBlobLoader` (azure-storage-blob SDK).
- `backend/app/indexing/splitter.py`: `MarkdownHeaderTextSplitter` → `RecursiveCharacterTextSplitter` (512 tokens, 80 overlap, tiktoken cl100k_base).
- `backend/app/indexing/embeddings.py`: `GeminiEmbeddingsAdapter` (google-genai SDK, batching, tenacity backoff exponencial, L2 normalización tras MRL 3072→1536).
- `backend/app/indexing/store.py`: `PgVectorChunkStore` (upsert `ON CONFLICT DO NOTHING` en `chunk_hash`).
- `backend/app/indexing/pipeline.py`: `run_indexing()` — orquestador blob→split→embed→store.
- `backend/migrations/versions/0001_create_chunks_table.py`: tabla `chunks` (vector(1536), jsonb, tsvector), HNSW cosine (m=16, ef_construction=64), GIN en `content_tsv`, índice en `corpus_sha`.
- Tests unitarios: 33/33 verdes — `test_embeddings` (11), `test_models` (5), `test_pipeline` (8), `test_splitter` (8), `test_health` (1).

### Cambiado
- `backend/app/config.py`: añadido `azure_storage_connection_string`.
- `backend/pyproject.toml`: dependencias de indexación añadidas (langchain, langchain-text-splitters, langchain-google-genai, google-genai, azure-storage-blob, tenacity, tiktoken, numpy, pytest-asyncio).
- `docker-compose.yml`: `AZURE_STORAGE_CONNECTION_STRING` pasado al backend.
- `.env.example`: añadidas `AZURE_STORAGE_CONNECTION_STRING` y `BATCH_SIZE`.

### Decisiones documentadas
- Spec 01 implementada. ADR-002 (pgvector) y ADR-003 (Azurite) aplicados.
- Se migró de `google-generativeai` (deprecado) a `google-genai >= 1.0`.
- `content_tsv` no es columna `GENERATED ALWAYS`: el store la computa en el INSERT via `to_tsvector('english', content)`.

### Notas
- Indexación real validada: 144 blobs → 1 775 chunks spliteados → **1 765 chunks únicos** en pgvector (10 deduplicados por contenido idéntico entre ficheros; comportamiento correcto de `ON CONFLICT DO NOTHING`). Segunda pasada: `chunks_inserted=0` — idempotencia confirmada. Tabla limpia: único `corpus_sha = 40e33e4...`.

---

## [Bloque A] — 2026-05-21

### Añadido
- `backend/`: app FastAPI con endpoint `/health`, tests (Pytest), `pyproject.toml` gestionado con uv, Dockerfile y Alembic inicializado (motor de migraciones, sin revisiones aún).
- Paquetes por feature en `backend/app/` (auth, chat, indexing, retrieval, evals, security, observability) según ADR-011.
- `frontend/`: app Vite + React + TypeScript con `Dockerfile.dev`.
- `infra/postgres/init.sql` con `CREATE EXTENSION vector`.
- `docker-compose.yml` (raíz) con 5 servicios (postgres+pgvector, azurite, phoenix, backend, frontend), healthchecks y volúmenes persistentes.
- `.env.example` (`GOOGLE_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`, `PHOENIX_COLLECTOR_ENDPOINT`), `README.md` con quickstart y CI base en `.github/workflows/ci.yml`.
- husky + commitlint con hook `commit-msg` para validar Conventional Commits.
- Directorios `corpus/`, `prompts/`, `scripts/`, `security/`.

### Decisiones documentadas
- `docker-compose.yml` en la raíz (no en `infra/`) para que `docker compose up -d` funcione sin `-f` y casar con el quickstart de `CLAUDE.md`.

### Notas
- Stack verificado: 5/5 servicios sanos, `pgvector` 0.8.2 instalado, commitlint rechaza mensajes malformados.

---

## Plantilla por bloque

```markdown
## [Bloque X] — YYYY-MM-DD

### Añadido
- ...

### Cambiado
- ...

### Eliminado
- ...

### Decisiones documentadas
- ADR-XXX: <título>
- Spec: <nombre>

### Notas
- ...
```
