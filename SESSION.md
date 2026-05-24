# SESSION.md — Estado de la sesión actual

> Fichero dinámico. Se actualiza al inicio y al final de cada sesión de construcción. Cualquier agente que abra el repo lea este fichero para saber dónde se quedó el trabajo.

## Bloque actual

**Bloque:** Z (Release v1.0.0 — cierre operativo, no feature)
**Estado:** in_progress
**Fecha apertura:** 2026-05-24 (sesión 13)
**Última actualización:** 2026-05-24 (sesión 13)

> Bloque S completado ✓ (merge squash PR #19 + tag `10-block-S`). El histórico de bloques anteriores en CHANGELOG.md.

## Objetivo del bloque

Cierre de la v1.0.0: documentación de release (C4 L3, README, DECISIONS), limpieza (TODOs, `.env.example`, secretos), verificación end-to-end desde clone fresco y preparación del tag anotado `v1.0.0` + cuerpo del release. No es un bloque de feature: no se añade funcionalidad.

## Próxima acción concreta

Gate humano: revisar el PR de cierre, mergear en squash, crear el tag anotado `v1.0.0` y publicar el release. No tagear ni publicar por agente.

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
