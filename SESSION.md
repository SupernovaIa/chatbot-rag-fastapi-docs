# SESSION.md — Estado de la sesión actual

> Fichero dinámico. Se actualiza al inicio y al final de cada sesión de construcción. Cualquier agente que abra el repo lea este fichero para saber dónde se quedó el trabajo.

## Bloque actual

**Bloque:** S (Seguridad)
**Estado:** gate_pending
**Fecha apertura:** 2026-05-24 (sesión 12)
**Última actualización:** 2026-05-24 (cierre de sesión 12)

> Bloque F completado ✓ (merge squash PR #18 + tag `09-block-F`). El histórico de bloques anteriores en CHANGELOG.md.

## Objetivo del bloque

Defense in depth en 5 capas frente a prompt injection, jailbreaks y fuga de información (spec `09-security-layers.md`, OWASP LLM01/LLM02). Red team con ≥18/20 prompts bloqueados, ≥3 de injection indirecta.

## Próxima acción concreta

Gate humano: merge squash de la PR + tag `10-block-S`. No mergear ni taggear por agente.

## Pendientes en este bloque

- [x] Capa 1 · Safety filters de Gemini (`BLOCK_MEDIUM_AND_ABOVE` en 4 categorías) + detección de bloqueo por `finish_reason`
- [x] Capa 2 · Guardrail Flash (`prompts/guardrail.md` + `app/security/guardrail.py`, clasifica legitimate/suspicious/hostile, fail-open)
- [x] Capa 3 · System prompt robusto (`prompts/system.md` v1.3 + `<context>` como datos no confiables en `prompts.py`)
- [x] Capa 4 · Filtro de output (`app/security/output_filter.py`, regex PII con Luhn + redaction incremental con holdback para streaming + detección de leak)
- [x] Capa 5 · Incidentes en Phoenix (`app/security/incidents.py`, span `security_incident` con `blocking_layer`) + rate limiting por `user_id` 30/min (`app/security/rate_limit.py`, vía `limits`)
- [x] `security/red-team-checklist.md` (20 hostiles + 3 controles, ≥3 injection indirecta) + `scripts/red_team.py` conectado a `/redteam`
- [x] Red team contra sistema real: **20/20 bloqueados** (4/4 injection indirecta, 3/3 controles sin falso positivo)
- [x] Tests `backend/tests/security/` + integración de bloqueo/redaction en `tests/chat/test_router.py`

## Completado en esta sesión (Bloque S, sesión 12)

- [x] Primer commit de rama: `SESSION.md` — F marcado como completado, S como in_progress; spec 09 commiteada.
- [x] `backend/app/security/` — `models.py` (BlockingLayer, Verdict, GuardrailVerdict, OutputScanResult), `safety.py`, `guardrail.py`, `output_filter.py`, `incidents.py`, `rate_limit.py`.
- [x] `backend/app/chat/generator.py` — `safety_settings` en `ChatGoogleGenerativeAI`; captura `finish_reason`; flag `safety_blocked`.
- [x] `backend/app/chat/router.py` — guardrail pre-retrieval (hostile → respuesta segura, suspicious → flag), redaction PII del stream, detección de leak post-stream, persistencia del texto redactado, `rate_limited_user` (auth declarada **primero** para preservar el 401), incidentes por capa.
- [x] `backend/app/main.py` — rate limiting movido a dependencia (sin `BaseHTTPMiddleware`, que rompía el 401 temprano).
- [x] `prompts/system.md` v1.3 (sección de seguridad), `prompts/guardrail.md` v1.0, `prompts.py` (delimitadores `<context>`).
- [x] `security/red-team-checklist.md`, `scripts/red_team.py`, `.claude/commands/redteam.md` (conectado al script).
- [x] `backend/pyproject.toml` — dep `slowapi>=0.1.9` (usa `limits`); `app/config.py` — settings de seguridad.
- [x] Tests: `backend/tests/security/test_output_filter.py`, `test_guardrail.py`, `test_safety_and_incidents.py` + `TestSecurityLayers` en `tests/chat/test_router.py`.

## Verificación pre-cierre (sesión 12, Bloque S)

- `cd backend && uv run ruff check . ../scripts/red_team.py` → `All checks passed!` ✓
- `cd backend && uv run pytest -q` → `279 passed` ✓
- `python scripts/red_team.py` contra el stack real → **block rate 20/20** (gate ≥18/20), 4/4 injection indirecta, 3/3 controles ✓ (ver `security/red-team-results.md`)
- Spans `security_incident` en Phoenix con `blocking_layer`/`blocking_layer_name` verificados (GUARDRAIL + OUTPUT_FILTER) ✓

> **Notas:**
> - El guardrail es un LLM (Flash) y tiene varianza; el free-tier devuelve a veces respuestas vacías/error transitorias. `red_team.py` reintenta una vez ante vacío/error para que el gate refleje la postura real, no la flakiness. Defensa en profundidad: aunque el guardrail dejara pasar un caso, la capa 3 (system prompt) también rechaza.
> - Rate limiting en memoria (single-worker dev/free-tier). Para escalar a varios workers: cambiar `MemoryStorage` por `RedisStorage`.

## Gate de revisión (Bloque S)

- **Criterio:** 5 capas implementadas según spec 09; `red_team.py` bloquea ≥18/20 sin fugar PII ni system prompt; ≥3 injection indirecta neutralizada; incidentes con `blocking_layer` en Phoenix; rate limiting por `user_id`.
- **Resultado:** **pendiente** (gate humano — merge PR + tag `10-block-S`).

## Blockers

Ninguno.
