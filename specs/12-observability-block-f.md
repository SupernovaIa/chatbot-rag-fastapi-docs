# Spec 12 — Observabilidad consolidada (Bloque F)

**Fecha:** 2026-05-24
**Bloque:** F
**Estado:** in_progress

## Goal

Cerrar los huecos de observabilidad abiertos en el bloque CH (TODO block-F en `router.py`) y añadir la capa de coste económico. Al terminar, cada turno de chat emite un árbol de spans completo en Phoenix con latencia por fase, tokens (input / cached / output), TTFT y coste estimado en USD.

## User story

Como estudiante revisando el comportamiento del pipeline, quiero ver en Phoenix un span `chat_turn` padre con sus hijos (`chat_retrieve` → `retrieve` → `rewrite`/`hybrid_search`/`rerank`) y un span `generate` con los contadores de tokens y TTFT, para entender el rendimiento y el coste de cada turno.

## Approach

1. **Spans manuales**: `chat_turn` se inicia en el route handler, captura el contexto OTel y lo pasa a la closure `event_generator()` vía `set_span_in_context`. El span termina al final del generador (en un bloque `finally`).
2. **Span `generate`**: también manual, iniciado dentro del generador como hijo de `chat_turn`. Captura TTFT (tiempo al primer token), y al terminar el stream registra `prompt_tokens`, `cached_tokens`, `output_tokens`, `cost_usd`.
3. **Módulo de coste**: `backend/app/observability/cost.py` centraliza el pricing de Gemini (anchored al 2026-05-20). `compute_cost(usage, model)` devuelve un `QueryCost` dataclass. Adjunto al span `generate` y registrado en el log.
4. **Dashboards**: 3 ficheros JSON en `infra/phoenix/dashboards/` con las definiciones de panel (formato de consulta sobre la API OTel de Phoenix). `scripts/setup_phoenix_dashboards.py` los importa vía Phoenix REST API.
5. **Caching impact**: `scripts/measure_caching_impact.py` lanza N turnos consecutivos con el mismo contexto, recoge `cached_content_token_count` de la API y genera el informe `docs/caching-impact.md`.
6. **`/dashboard`**: actualizar el comando para consultar `GET /v1/spans` de Phoenix y renderizar un resumen en Markdown.

## Acceptance criteria

- [ ] Cada turno de chat emite en Phoenix un span `chat_turn` padre con hijos correctamente anidados.
- [ ] El span `generate` contiene: `prompt_tokens`, `cached_tokens`, `output_tokens`, `ttft_ms`, `model`, `cost_usd`.
- [ ] `backend/app/observability/cost.py` expone `compute_cost(usage, model) → QueryCost`; todos los paths cubiertos con tests.
- [ ] `docs/cost-model.md` documenta el modelo de pricing con versión y fecha.
- [ ] `infra/phoenix/dashboards/` contiene 3 ficheros JSON (health, quality, cost).
- [ ] `scripts/measure_caching_impact.py --help` funciona; `docs/caching-impact.md` documenta la metodología y los números del bloque.
- [ ] El slash `/dashboard` consulta Phoenix, renderiza la tabla de métricas de las últimas 24h y destaca fases lentas.
- [ ] `uv run ruff check .` limpio; `uv run pytest` verde (≥ 218 tests previos + nuevos de cost).

## Dependencies

- Bloque CH: `UsageMeta` ya captura `cached_content_token_count`.
- Bloque R: spans de retrieval ya instrumentados (`rewrite`, `hybrid_search`, `rerank`, `retrieve`).
- Bloque E: `evals.run` span ya existe.

## Risks

- **Contexto OTel entre threads**: `asyncio.to_thread` copia los `contextvars` de la tarea llamadora, por lo que el contexto de `chat_turn_span` se propaga correctamente a los sub-spans del retrieval. Verificar en integración.
- **Implicit caching de Gemini**: el campo `cached_content_token_count` puede ser `None` en streaming (issue #12 del bloque CH). El módulo de coste trata `None` como 0 y registra `caching_available: False` en el span.
- **Phoenix versión**: el docker-compose usa `arizephoenix/phoenix:latest`. La API REST v1 de spans es estable desde Phoenix 4.x. Si el endpoint cambia, el `/dashboard` degrada gracefully.
