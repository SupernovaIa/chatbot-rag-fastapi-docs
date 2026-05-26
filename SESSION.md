# SESSION.md — Estado de la sesión actual

> Fichero dinámico. Se actualiza al inicio y al final de cada sesión de construcción. Cualquier agente que abra el repo lea este fichero para saber dónde se quedó el trabajo.

## Bloque actual

**Bloque:** EV2 (Evolutivo post-1.0 — retrieval gating)
**Estado:** in_progress
**Fecha apertura:** 2026-05-26 (sesión 15)
**Última actualización:** 2026-05-26 (sesión 15)

> Bloque EV1 completado ✓ (borrado de conversaciones, PR #22, tag `EV1-block`). Bloque Z completado ✓ (release v1.0.0). El histórico de bloques anteriores en CHANGELOG.md.

## Objetivo del bloque

Segundo evolutivo (cierre v1.2.0): **retrieval gating**. Antes del pipeline rewrite→retrieve→rerank, decidir si la consulta necesita recuperar contexto del corpus. Para saludos, agradecimientos, meta-preguntas sobre la propia conversación y follow-ups resolubles con el historial, saltar retrieval y responder directo. Objetivo medible: bajar latencia y coste por turno en los casos sin retrieval **sin que las evals de calidad regresen** (eval gate como red de seguridad antes de cerrar).

Decisión arquitectónica (ADR-013): **clasificador Gemini Flash** (intención) que corre **concurrente** con el guardrail de capa 2 vía `asyncio.gather`, de modo que la latencia de la ruta de entrada es `max(guardrail, intent)` ≈ un round-trip, no la suma. Puerto fino propio (`IntentGate`) separado del guardrail, prompt versionado en `prompts/`, **fail-open hacia retrieve** (el falso salto es el fallo caro). Rechazados en el ADR: heurístico (frágil ante lenguaje natural/paráfrasis/idiomas) y Flash secuencial (dobla la latencia de entrada).

## Próxima acción concreta

Escribir `specs/14-retrieval-gating.md` + `docs/adr/ADR-013-retrieval-gating.md` → implementar `IntentGate` (puerto + adaptador Flash + prompt) → cablear concurrencia `gather(guardrail, intent)` en `router.py` + camino de prompt sin contexto para turnos saltados (sin tocar reglas capa 3 de system v1.3) → verificar en vivo (saludo salta / pregunta técnica recupera / follow-up) → tests con Gemini mockeado → eval gate. Cierre: commits divididos, abrir PR y parar (gate humano).

## Pendientes en este bloque

- [x] Primer commit de rama: `SESSION.md` — S marcado como completado, Z (release) como in_progress.
- [x] C4 Level 3: `docs/architecture/04-components.md` (componentes del backend).
- [x] Reescritura de `README.md` (qué es, stack, quickstart 5 pasos, evals/red team, árbol, roadmap v1.1, anexo Azure).
- [x] `DECISIONS.md` revisado: 11 ADRs indexados + ADR-012 (gate de evals determinista/nocturna, surgido en E).
- [x] Limpieza: 0 TODOs/FIXMEs en código; `.env.example` completo (+ ENVIRONMENT, CORS_ORIGINS); `.gitleaks.toml` con allowlist documentada → escaneo limpio.
- [x] **fix descubierto en la verificación:** `scripts/` no estaba montado en el contenedor; los comandos documentados fallaban. Se añade `./scripts:/app/scripts:ro` en compose y se corrigen los comandos del README.
- [x] Verificación end-to-end desde clone fresco (ver evidencia abajo).
- [x] Mensaje del tag anotado `v1.0.0` + cuerpo del release preparados en `docs/release/v1.0.0.md` (no publicados).

## Verificación end-to-end desde clone fresco (sesión 13)

Ejecutada con `docker compose down -v` y stack reconstruido desde cero. Evidencia real:

1. **Reset + arranque:** `down -v` borra volúmenes; `up -d --build` → 5/5 servicios `healthy`.
2. **Indexado:** `alembic upgrade head` (3 migraciones) → `upload_corpus` (145 blobs) → `index_corpus` → **145 blobs / 1782 chunks split / 1772 en pgvector** (~51 s).
3. **Auth + multi-turn:** register 201 → login 204 (cookie `access_token`) → `/auth/me` 200. Conversación de **5 turnos** sobre la misma sesión: cada turno responde con marcadores `[1]`–`[5]` mapeados a **5 citas reales**; el rewriter resuelve el contexto multi-turn (turno 2 "¿y su tipo?" → *Path parameters with types*; turno 5 combina path+query).
4. **/eval:** gate determinista `ci_subset --retrieval-only` → **PASS** (recall@5 1.000, MRR 0.883; floors 0.85; exit 0).
5. **/redteam:** `red_team.py` contra el sistema real → **20/20 bloqueados** (gate ≥18/20), 4/4 inyección indirecta neutralizada, 3/3 controles sin falso positivo.
6. **Phoenix:** **331 spans** — `chat_turn` 42, `generate` 27, `retrieve`/`rerank`/`hybrid_search`/`rewrite` 27 c/u, `ChatGoogleGenerativeAI` 108, `security_incident` 19 (15 GUARDRAIL + 4 OUTPUT_FILTER, con `blocking_layer`).
7. **CI bloquea regresión:** PR #20 (deliberada, `retrieval_candidates=1`) → **Eval gate FAIL** (recall@5/MRR 0.500 < 0.85, exit 1) + 2 tests unitarios rojos. PR cerrada sin mergear, rama borrada.

> Tests: `279 passed`, ruff limpio. gitleaks: `no leaks found` con `.gitleaks.toml`.

## Gate de revisión (Bloque Z)

- **Criterio:** documentación de release completa y coherente; sin secretos reales (gitleaks limpio); tests verdes; verificación end-to-end desde clone fresco con evidencia real de cada paso.
- **Resultado:** **pendiente** (gate humano — merge PR + tag anotado `v1.0.0` + release).

## Blockers

Ninguno.
