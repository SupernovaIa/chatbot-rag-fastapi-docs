# SESSION.md — Estado de la sesión actual

> Fichero dinámico. Se actualiza al inicio y al final de cada sesión de construcción. Cualquier agente que abra el repo lea este fichero para saber dónde se quedó el trabajo.

## Bloque actual

**Bloque:** E (Evaluación + CI con gate del PR)
**Estado:** in_progress
**Fecha apertura:** 2026-05-23 (sesión 9)
**Última actualización:** 2026-05-23 (apertura de sesión 9)

> Bloque D completado ✓ (tag `07-block-D` pendiente de merge humano). Bloque AU completado ✓ (tag `06-block-AU` pendiente de merge humano). Bloque CH completado ✓ (tag `05-block-CH` pendiente de merge humano). Bloque R completado ✓ (tag `04-block-R` pendiente de merge humano). Bloque G completado ✓ (tag `03-block-G` · PR #5). Bloque B completado ✓ (tag `02-block-B`). El histórico se conserva más abajo.

## Objetivo del bloque

Evaluación automática del pipeline RAG (Spec 10 / ADR-007): módulo `backend/app/evals/` (loader del gold, runner del pipeline, métricas deterministas recall@5/MRR, juez RAGAS con Gemini Pro, report markdown vs baseline, `thresholds.yaml`); tests Pytest parametrizados sobre el gold con subset `ci_subset`; conectar el slash `/eval`; workflows `eval.yml` (gate del PR) y `eval-nightly.yml` (suite completa). Gate humano entre el código y el cableado de CI: medir baseline, acordar estrategia del gate y validar el juez.

## Próxima acción concreta

Gate humano **cerrado** (sesión 10): thresholds fijados, baseline definitivo medido y pinneado, CI cableado con caché de índice, branch protection activa y secret `GOOGLE_API_KEY` puesto. Al reanudar: **merge humano de la PR #17** (squash) tras ver el check `Eval gate (ci_subset)` en verde, y crear el tag `08-block-E`. No mergear ni taggear por agente.

## Pendientes en este bloque

- [ ] Merge humano de PR #17 (squash) + tag `08-block-E`.
- [ ] (v1.1) Abstención por flag estructurado del generador en vez de match por strings (la detección actual no reconoce "no tengo **suficiente** información"; es advisory, no bloquea).
- [ ] (seguimiento) El rerank listwise tarda p50 ~10s incluso con 8 candidatos; si crece la latencia, decidir en ADR si se cambia de enfoque (no subir el deadline por encima de 15s).

## Gate humano — decisiones y hallazgos (sesión 10)

**Hallazgos destapados al medir contra la API real (ninguno lo pillaban los tests por ir mockeados):**
- **Drift de deadlines de la API.** Gemini exige deadline ≥10s; los valores de spec 03 (rerank 5s, rewrite 1.5s) daban 400 → el reranker/rewriter caían **siempre** al fallback. Con 20/10 candidatos seguía dando 504 (p95 ~123s por reintentos del SDK). Fix: 8 candidatos, timeout 15s, `max_retries=0` → p50 10.0s / p95 10.9s, 0/7 fallbacks.
- **Idioma.** La generación respondía en inglés en parte de los turnos (contexto inglés, prompt sin regla de idioma). Fix: prompt v1.2 fuerza español. faithfulness 0.84→0.95 tras el fix.
- **Modelo del juez.** `gemini-3-pro` daba 404; el id real es `gemini-3-pro-preview`.
- **Abstención.** El detector por strings (solo ES) marcaba falso negativo; añadidos marcadores EN. Sigue siendo frágil (TODO v1.1: flag estructurado). Es advisory.
- **recall@5 vs multi_source.** El match determinista por `(source, section)` da 0 cuando la info está en chunks no-gold (g-24), aunque la respuesta sea correcta. Por eso recall@5/MRR pasan a **advisory**; el gate bloquea solo sobre las 4 métricas del juez.

**Estrategia del gate acordada:**
- Floors del juez: faithfulness 0.80, answer_relevancy 0.70, context_precision 0.80, context_recall 0.85.
- Regresión **absoluta**: bloquea si una métrica del juez cae >0.07 vs el baseline de `main`.
- recall@5 / MRR / abstención: advisory (no bloqueantes).
- **Subset del gate del PR = 6 ejemplos** (`CI_GATE_IDS`: g-01, g-03, g-16, g-24, g-31, g-36) por presupuesto de tiempo de CI (el `ci_subset` de 14 se iba a ~13-14 min; ver nota en spec 10). Baseline pinneado sobre esos 6 (5 answerable, rerank vivo, prompt v1.2): faithfulness 1.0 · answer_relevancy 0.847 · context_precision 0.99 · context_recall 1.0. La nocturna corre los 40 + refresca el baseline del gate sobre `ci_gate`.

**Latencia/coste del gate del PR:** CI usa `max_workers=6` + caché de índice (actions/cache keyed por hash del corpus + modelo de embeddings; el embedding cuesta ~40 s, no es el cuello de botella). `timeout-minutes: 12` como kill switch.

**Verificación del gate (determinista, sin cuota):** ✅ healthy PASS; regresión de faithfulness 0.10 BLOQUEA; answer_relevancy bajo floor BLOQUEA; context_recall −0.10 BLOQUEA; recall@5 hundido NO bloquea (advisory). Nota: con baseline faithfulness=1.0 y regresión 0.07, la banda efectiva de faithfulness es [0.93, 1.0] (los valores sanos medidos ~0.94-0.95 pasan, con poco margen); la nocturna re-mide y estabiliza el baseline.

**Verificación live en CI: ⏳ bloqueada hoy por cuota.** El juez Gemini 3 Pro free-tier quedó throttleado tras los muchos runs del gate de hoy (1/20 trabajos en 11 min, resto `TimeoutError`), así que el run del gate en la PR #17 se canceló por timeout. Es un estado transitorio de cuota, NO un fallo de diseño. **Pendiente:** re-ejecutar el check `Eval gate (ci_subset)` en la PR #17 cuando la cuota Pro se reponga (reset diario) para confirmar el <10 min en vivo. El gate es **fail-safe**: un run throttleado se cancela (no pasa) → branch protection bloquea el merge hasta un run limpio.

**Branch protection:** `main` requiere los checks `Eval gate (ci_subset)` + `Backend lint + tests`. `enforce_admins=false` a propósito, para que el merge humano de la PR #17 no quede bloqueado por el check throttleado de hoy.

## Completado en esta sesión (Bloque E, sesión 9)

- [x] Primer commit de rama: `specs/10-evals-ci-gate.md` committeado; D marcado como completado, E como in_progress.
- [x] `backend/app/evals/loader.py` — `GoldExample`/`GoldChunk`, `load_gold`, `CI_SUBSET_IDS` (15 ej., cubre los 5 tipos), `select_subset` (falla si falta id).
- [x] `backend/app/evals/metrics.py` — `recall_at_k`, `reciprocal_rank` (match `(source, section)`), `is_abstention` (rechazo `no_se`), `mean`.
- [x] `backend/app/evals/models.py` — `ExampleRun`, `MetricScores`, `RunReport`.
- [x] `backend/app/evals/ports.py` — `AnswerGeneratorPort`, `JudgePort` (mockeables).
- [x] `backend/app/evals/generator.py` — `GeminiAnswerGenerator` (Flash, no streaming, reusa `build_prompt`).
- [x] `backend/app/evals/judge.py` — `RagasGeminiJudge` (Gemini Pro, RAGAS, `RunConfig` free-tier, import diferido, NaN-safe).
- [x] `backend/app/evals/runner.py` — `run_evals` orquesta retrieve→generate, agrega métricas, captura errores por-ejemplo.
- [x] `backend/app/evals/report.py` — `evaluate_gate` (floor + regresión relativa), `render_markdown`, `report_to_baseline`.
- [x] `backend/app/evals/thresholds.yaml` — floors provisionales + config de regresión.
- [x] `backend/app/evals/telemetry.py` — span Phoenix `evals.run` (métricas, subset, commit/corpus SHA).
- [x] `backend/app/evals/cli.py` — `python -m app.evals.cli` (subset/baseline/markdown/json/no-judge); exit 0/1/2.
- [x] `backend/app/config.py` — `gemini_pro_model`, `evals_judge_max_workers`, `evals_judge_timeout_s`, `evals_gen_timeout_s`.
- [x] `backend/pyproject.toml` — `ragas>=0.2,<0.3`, `pyyaml`; markers `ci_subset`/`evals_live`. `uv.lock` actualizado.
- [x] `backend/tests/evals/` — 71 tests (loader, metrics, runner con fakes, report/gate, pipeline parametrizado con `ci_subset`).
- [x] `.claude/commands/eval.md` — `/eval` cableado al runner.
- [x] `.github/workflows/eval.yml` — gate del PR (Postgres + Azurite services, indexa corpus, subset `ci_subset`, comenta el PR, bloquea merge; guard si falta el secret).
- [x] `.github/workflows/eval-nightly.yml` — suite completa nocturna + `workflow_dispatch`; refresca `baseline_metrics.json` en `main`.

## Verificación pre-cierre (sesión 9, Bloque E)

- `cd backend && uv run ruff check .` → `All checks passed!` ✓
- `cd backend && uv run pytest -q` → `218 passed` (147 previos + 71 nuevos de evals) ✓
- `uv run pytest tests/evals/test_pipeline.py -m ci_subset --co` → 14 tests, cubren los 5 tipos ✓
- `python -m app.evals.cli --help` → OK ✓
- YAML de ambos workflows + `thresholds.yaml` parsean ✓

> **Nota sobre lo NO verificable aquí:** el flujo live (indexar + retrieve + juez Gemini Pro) y la medición del baseline requieren stack Docker + `GOOGLE_API_KEY`. Es justo el contenido del gate humano de la spec. Pendiente para Javi.

## Gate de revisión (Bloque E)

- **Criterio (Spec 10):** runner + tests primero; medir baseline; acordar estrategia del gate; validar el juez; solo entonces cablear CI a producción (branch protection + secret).
- **Resultado:** **pendiente** (gate humano). Código, tests y workflows listos. Pasos humanos:
  1. `docker compose up -d` + `/index`; correr `docker compose exec backend python -m app.evals.cli --subset ci_subset --no-judge` para validar retrieval, y luego sin `--no-judge` con un subset reducido para generar `baseline_metrics.json` (`--update-baseline`).
  2. Spot-check humano de ~8 ejemplos del juez (faithfulness/relevancy) antes de confiarle el gate (ADR-007).
  3. Acordar la estrategia (floor absoluto vs floor + regresión) y fijar los valores definitivos en `thresholds.yaml`.
  4. Añadir el secret `GOOGLE_API_KEY` en el repo y activar branch protection con `Eval gate (ci_subset)` como check requerido.

## Completado en esta sesión (Bloque D, sesión 8)

- [x] Primer commit de rama: `specs/11-frontend-chat.md` committeado; AU marcado como completado, D como in_progress.
- [x] `frontend/index.html` — Google Fonts: Poppins (400/500/600) + JetBrains Mono (400/500).
- [x] `frontend/src/index.css` — CSS variables del design system (`--bg`, `--fg`, `--accent`, `--highlight`, `--muted`, `--green`, `--danger`, `--orange`); tipografía Poppins/JetBrains Mono; estilos `.prose` para markdown (pre, code, blockquote, table, ul/ol); `.citation-chip`; `.streaming-cursor` con animación blink; `@keyframes spin` para botón de envío.
- [x] `frontend/src/main.tsx` — importa `index.css`.
- [x] `frontend/src/api/chat.ts` — tipos `Citation`, `SessionOut`, `MessageOut`, `SessionDetailOut`; funciones `listSessions()` y `getSession(sessionId)`.
- [x] `frontend/src/hooks/useChatStream.ts` — hook que consume `POST /chat/` como SSE vía `fetch` + `ReadableStream`; gestiona `AbortController` (cancela en unmount y al iniciar nueva petición); parsea líneas `data: <json>` de sse_starlette; callbacks `onToken`, `onCitations`, `onDone`; expone `streaming`, `error`, `sendMessage`, `cancel`.
- [x] `frontend/src/components/ChatInput.tsx` — textarea + botón enviar; `Enter` envía, `Shift+Enter` inserta salto; deshabilitado durante streaming; spinner animado en botón; focus states accesibles.
- [x] `frontend/src/components/MessageList.tsx` — lista scrollable con `aria-live`; auto-scroll al bottom en cada cambio; estado vacío; indicador de loading (dots animados) antes del primer token.
- [x] `frontend/src/components/Message.tsx` — burbujas usuario (derecha, `#eef6f3`) y asistente (izquierda, transparente); markdown con `react-markdown` + `remark-gfm` + `rehype-sanitize`; cuando llegan citations, `[N]` se convierten en `.citation-chip` clicables con `renderWithCitationChips`; cursor de streaming animado; XSS: `<script>` y handlers `on*` eliminados por `rehype-sanitize`.
- [x] `frontend/src/components/CitationsPanel.tsx` — panel deslizante fijo (derecha); muestra `section`, `source` (enlace) y `chunk_hash` truncado; lista de todas las citas con resaltado de la activa; cierre con botón ✕ o tecla Escape; backdrop click-to-close; `aria-label` + focus en apertura.
- [x] `frontend/src/components/SessionSelector.tsx` — sidebar izquierda; carga `GET /chat/sessions` en mount y ante `refreshTrigger`; ordena por `updated_at` desc; botón "Nueva conversación"; sesión activa resaltada; manejo de error y estado vacío.
- [x] `frontend/src/pages/ChatPage.tsx` — reescritura completa: header con badge RAG + email + botón salir; layout sidebar + chat-area; integra `SessionSelector`, `MessageList`, `ChatInput`, `CitationsPanel`; gestión de `currentSessionId` con `crypto.randomUUID()` para nuevas sesiones (idempotente en backend); `refreshTrigger` post-turno; `loadSession` reconstruye mensajes desde historial; indicador de error SSE.
- [x] `frontend/nginx.conf` — config nginx: SPA fallback `try_files`; `location /api/` proxy a `http://backend:8000/`; `proxy_buffering off` + `proxy_http_version 1.1` para SSE token-a-token.
- [x] `frontend/Dockerfile.prod` — multi-stage: `node:22-alpine` build con `VITE_API_URL=/api`; `nginx:1.27-alpine` serve; `dist/` copiado al webroot de nginx.
- [x] `docker-compose.yml` — servicio `frontend-prod` (puerto 80, `Dockerfile.prod`, `profiles: [prod]`).
- [x] `frontend/package.json` + `package-lock.json` — nuevas deps: `react-markdown@^9.1.0`, `rehype-sanitize@^6.0.0`, `remark-gfm@^4.0.1`.
- [x] **Fix review #1 — citations scoping por mensaje**: `onCitationClick(idx, citations)` ahora lleva el array `citations` del propio mensaje; `renderWithCitationChips` lo pasa hacia arriba; `ChatPage.handleCitationClick` lo usa directamente. Eliminados `findLastCitations` y el `useEffect` de sincronización de `activeCitations`. Verificado en vivo con conversación de 2 turnos (sources distintos por turno).
- [x] **Fix review #2 — eliminar DOM event bus**: `CitationsPanel` recibe `onSelectIndex: (i: number) => void` como prop y lo llama directamente; eliminado `document.dispatchEvent(CustomEvent)`. `ChatPage` pasa `onSelectIndex={setSelectedCitationIndex}` y elimina el `document.addEventListener("select-citation", ...)`.
- [x] `Makefile` — `make dev` / `make prod` / `make down` como atajos de `docker compose`.
- [x] Issue #16 abierto con los findings 🟡🟢 del review (dead ref, double refresh, SyntaxError frágil, silent error, dots blink, type cast, reader cleanup, gzip).

## Decisiones tomadas en este bloque (D)

- **SSE vía `fetch` (no `EventSource`)**: `EventSource` sólo soporta GET; el endpoint `/chat/` es POST con body. Se lee `ReadableStream` directamente y se parsean líneas `data:`. Cancelación por `AbortController`.
- **Session UUID client-side (`crypto.randomUUID()`)**: El backend acepta `session_id: UUID | None`; si se pasa un UUID que no existe, lo crea (idempotente). Así el frontend sabe el ID de la sesión desde el primer turno, sin necesidad de un campo extra en la respuesta SSE.
- **`rehype-sanitize` con schema por defecto**: El schema por defecto no incluye `<script>` ni atributos `on*` en ningún elemento. Verificado programáticamente. Protege contra XSS desde contenido de chunks.
- **`[N]` chips via split**: La función `renderWithCitationChips` divide el texto en `[N]` y fragmentos de markdown. Cada fragmento va a una instancia de `ReactMarkdown` con `p → <>{children}</>` para evitar p anidados. No requiere plugins remark/rehype extra.
- **`refreshTrigger` para SessionSelector**: Después de cada `onCitations` y `onDone`, se incrementa un contador que pasa como prop a `SessionSelector`. Éste tiene un `useEffect([refreshTrigger])` que re-fetch las sesiones. Simple y sin contexto global.
- **`frontend-prod` como perfil separado**: El servicio dev (`frontend`) queda sin perfil (arranca por defecto). El servicio prod (`frontend-prod`) tiene `profiles: [prod]` para no mezclarse. Se activa con `docker compose --profile prod up` o `make prod`.
- **Citations scoping por mensaje (fix #1)**: `onCitationClick` lleva `(idx, citations)` — el array de citas del mensaje clickado, no una búsqueda global. `ChatPage` usa ese array directamente para abrir `CitationsPanel`.
- **Props React en lugar de DOM events (fix #2)**: `CitationsPanel.onSelectIndex` prop sustituye al `CustomEvent("select-citation")`. Elimina el acoplamiento implícito entre componentes hermanos a través del DOM.

## Blockers

Ninguno.

## Verificación pre-cierre (sesión 8, Bloque D)

- `cd backend && uv run ruff check .` → `All checks passed!` ✓
- `cd backend && uv run pytest tests/ -q` → `147 passed` ✓
- `npx commitlint --from $(git merge-base HEAD main) --to HEAD` → exit 0 ✓

## Verificación por agente (sesión 8, Bloque D)

| Check | Evidencia | Resultado |
|---|---|---|
| 1. `tsc --noEmit` | Sin errores de tipo | ✅ |
| 2. `npm run build` (dev + prod) | `311 modules transformed. ✓ built in ~700ms` | ✅ |
| 3. SSE por `curl -N` con cookie | `data: {"type": "token", ...}` × N + `data: {"type": "citations", ...}` | ✅ |
| 4. `GET /chat/sessions` con cookie | `[{"id": "...", "updated_at": "..."}]` | ✅ |
| 5. Sanitización XSS | `defaultSchema.tagNames` no incluye `script`; attrs `on*` ausentes | ✅ |

## Checklist de navegador para Javi (Spec 11 — verificación visual)

Requisito de la spec: "La parte visual la verifica Javi con una checklist corta que el agente deja preparada."

Arrancar el stack: `docker compose up -d`

1. **Register → chat**: Abrir `http://localhost:5173/register`, crear cuenta nueva → debe redirigir a `/` con la UI de chat.
2. **Login**: Cerrar sesión, ir a `/login`, iniciar sesión → redirige a `/`.
3. **Streaming token a token**: Escribir una pregunta y enviar. Los tokens deben aparecer progresivamente con el cursor naranja parpadeante; el botón debe estar deshabilitado durante el streaming.
4. **Citations chips**: Al terminar el stream, `[1]` `[2]` deben convertirse en chips verdes clicables. Hacer clic en uno → panel `CitationsPanel` se abre por la derecha con la sección y fuente.
5. **Multi-turno**: Sin cambiar de sesión, enviar una 2ª pregunta que implique contexto del turno anterior (ej. "¿Puedes ampliar lo anterior?"). La respuesta debe referenciar el contexto previo.
6. **Persistencia de sesiones**: Refrescar la página (`F5`). El `SessionSelector` debe mostrar las sesiones anteriores. Hacer clic en una → el historial de mensajes se carga correctamente.
7. **Nueva conversación**: Hacer clic en "+ Nueva conversación" → el área de chat se vacía; el siguiente envío crea una nueva sesión independiente.
8. **Logout**: Hacer clic en "Salir" → redirige a `/login`; navegar manualmente a `/` → redirige de nuevo a `/login`.
9. **Build de producción**: `docker compose --profile prod up -d frontend-prod`. Abrir `http://localhost:80`. Repetir flujo login → chat → streaming. El proxy `/api/*` debe funcionar transparentemente.
10. **XSS** (opcional, si el corpus tiene HTML en algún chunk): Comprobar en DevTools (Elements) que ningún `<script>` ni handler `onerror`/`onclick` aparecen en el DOM dentro de las burbujas del asistente.

---

## Gate de revisión (Bloque D)

- **Criterio (Spec 11):** flujo register→login→chat→multi-turno→logout en dev (`:5173`) y prod local (`:80`); stream token a token visible; chips `[N]` clicables abren CitationsPanel; sesiones persisten tras refresh; proxy `/api/*` resuelve en prod; chunks con HTML/script se renderizan como texto (XSS).
- **Resultado:** **pendiente** (gate humano).
  - ✓ TypeScript sin errores (`tsc --noEmit`).
  - ✓ Build de producción limpio (311 módulos, 365 KB JS gzippeado a 115 KB).
  - ✓ SSE `token` + `citations` verificado por curl contra stack real.
  - ✓ `GET /chat/sessions` verificado por curl.
  - ✓ `rehype-sanitize`: `<script>` y `on*` attrs fuera del schema.
  - ✓ 147 tests backend verdes. Ruff limpio.
  - ⏳ Flujo visual completo en navegador (checklist para Javi más arriba).

---

## Completado en sesiones anteriores (Bloque AU)

- [x] `backend/migrations/versions/0003_create_users_add_fk.py` — tabla `users` (id UUID PK, email UNIQUE, hashed_password, is_active, is_superuser, is_verified) + `CREATE UNIQUE INDEX ix_users_email` + FK `chat_sessions.user_id → users.id ON DELETE SET NULL`. Migración ejecutada contra stack Docker real.
- [x] `backend/app/auth/` — módulo completo (ADR-006): `models.py`, `schema.py`, `db.py`, `manager.py`, `router.py`. Dos cookies httpOnly: `access_token` (1 h) + `refresh_token` (7 d). `FastAPIUsers` + `current_active_user`. Rutas: `POST /auth/register|login|logout`, `GET /auth/me`, `POST /auth/refresh/login|logout`, `PATCH /auth/me`.
- [x] `backend/app/config.py` — `jwt_access_ttl_s`, `jwt_refresh_ttl_s`; `model_validator` falla si `environment != "development"` y `jwt_secret == "change-me"`; propiedad `cookie_secure`.
- [x] `backend/app/main.py` — `CORSMiddleware` + `auth_router`.
- [x] `backend/app/chat/store.py` — `save_turn` con `pg_advisory_xact_lock` (carrera cerrada); `list_sessions` filtra por `user_id`.
- [x] `backend/app/chat/router.py` — endpoints protegidos con `current_active_user`; scoping por usuario; `turn_idx` authoritative.
- [x] `backend/tests/auth/test_auth.py` — 10 tests (guards 401, scoping 403/200, filtrado de lista).
- [x] `frontend/src/api/auth.ts`, `hooks/useAuth.tsx`, `components/ProtectedRoute.tsx`, `pages/Login.tsx`, `pages/Register.tsx`, `App.tsx` — scaffold de auth completo.
- [x] 145 tests verdes. Ruff limpio. TypeScript sin errores.

## Gate de revisión (Bloque AU)

- **Resultado:** **pendiente** (gate humano).

---

## Completado en sesiones anteriores (Bloque CH)

- [x] `backend/migrations/versions/0002_create_chat_tables.py` — tablas `chat_sessions` y `chat_messages`. Constraint UNIQUE `(session_id, turn_idx, role)`.
- [x] `prompts/system.md` — system prompt versionado; ~1 200 tokens.
- [x] `backend/app/chat/` — models, store, prompts, generator, router (specs 05/06/07).
- [x] `backend/app/config.py` — `generate_timeout_s`, `history_window_n`.
- [x] `backend/app/main.py` — incluye `chat_router`.
- [x] 135 tests verdes al cierre de bloque CH. Ruff limpio. Verificación live con stack Docker real.

## Gate de revisión (Bloque CH)

- **Resultado:** **completado** ✓ (gate humano superado, merge squash + tag `05-block-CH` pendiente).

---

## Completado en sesiones anteriores (Bloque R)

- [x] `backend/app/retrieval/` — hybrid search, RankGPT reranker, query rewriter, orchestrator, LLM adapters, router.
- [x] `backend/app/observability/tracing.py` — OTel → Phoenix.
- [x] recall@5 = 0.867, hit-rate = 0.900, MRR = 0.801 (corpus_sha 40e33e4, 30 single-turn).

## Gate de revisión (Bloque R)

- **Resultado:** superado ✓.
