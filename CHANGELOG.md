# Changelog

Todos los cambios notables de este proyecto se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado según [SemVer](https://semver.org/lang/es/).

## [No publicado]

### Añadido (Bloque EV2 — Retrieval gating, hacia v1.2.0)

- `backend/app/chat/intent.py` — `IntentGate`, clasificador de intención sobre Gemini Flash (spec 14, ADR-013) que decide `needs_retrieval` antes del pipeline `rewrite→retrieve→rerank`. Puerto fino propio (recibe un `ChatLLMPort`), prompt versionado, parser JSON tolerante a fences/prosa, **fail-open hacia retrieve** ante cualquier error. `IntentVerdict(needs_retrieval, reason, failed_open)`.
- `prompts/intent_gate.md` v1.0 — prompt del gate: categorías que saltan (saludo, agradecimiento, meta-conversación, follow-up resoluble con historial) vs. recuperar (cualquier pregunta técnica de FastAPI); historial e input delimitados como datos; salida JSON; regla explícita "ante duda, retrieve".
- `docs/adr/ADR-013-retrieval-gating.md` + `DECISIONS.md` — decisión: clasificador Flash **concurrente** con el guardrail de capa 2 (`asyncio.gather`), de modo que la latencia de entrada es `max(guardrail, intent)`, no la suma. Rechazados: heurístico (frágil ante lenguaje natural) y Flash secuencial (dobla la latencia de entrada).
- `specs/14-retrieval-gating.md` — spec del evolutivo: goal, approach, criterios de aceptación, tests y riesgos.
- `backend/tests/chat/test_intent.py` — parser, true/false, fail-open ante excepción, inyección de query/historial.

### Cambiado (Bloque EV2)

- `backend/app/chat/router.py` — el historial se carga **read-only antes** de crear la sesión (para que el gate resuelva follow-ups y un input hostil no cree sesión vacía). Guardrail e intent gate se lanzan **concurrentes** (`asyncio.create_task` + `await`); en bloqueo del guardrail se cancela el intent. Si el gate decide saltar: no se llama a `retrieve`, `citations=[]`, prompt sin contexto; atributos `retrieval_skipped`/`intent_reason`/`intent_failed_open` en el span `chat_turn`. Nueva dependencia `get_intent_gate` (sin `max_retries`, mismo cuidado que el guardrail para no convertir un 401 en 500).
- `backend/app/chat/prompts.py` — `build_prompt_no_context(query, history)` para turnos saltados: reutiliza el **mismo** `system.md` v1.3 (capa 3 intacta) y solo cambia el turno humano (sin bloque `<context>`, respuesta conversacional).
- `backend/app/config.py` — settings `intent_gating_enabled` (default True) e `intent_timeout_s` (10s).
- `backend/tests/chat/test_router.py` / `test_prompts.py` — override de `get_intent_gate`; tests de turno saltado (no invoca retrieval, citas vacías) y turno técnico (sí recupera); `build_prompt_no_context` sin `<context>` y con system idéntico al RAG.

### Notas (Bloque EV2)

- **301 tests, todos verdes. Ruff limpio.** Verificación en vivo (curl: saludo salta / técnica recupera / follow-up) y eval gate como red de seguridad: pendientes del stack levantado / CI.

### Release v1.0.0 (Bloque Z — cierre operativo, no feature)

- `docs/architecture/04-components.md` — C4 Level 3: componentes del backend (auth, chat, retrieval, indexing, security, evals, observability) y su mapa a bloques de construcción.
- `README.md` — reescritura completa: qué es, stack en tabla, quickstart en 5 pasos, evals + red teaming, árbol del repo, roadmap v1.1 y anexo de despliegue en Azure (guía).
- `docs/adr/ADR-012-eval-gate-split.md` + `DECISIONS.md` — ADR del gate de evaluación determinista por PR + juez LLM en la nocturna (decisión surgida en el Bloque E, antes solo en el CHANGELOG).
- `.gitleaks.toml` — config con allowlist documentada de falsos positivos (clave pública de desarrollo de Azurite, JWT de ejemplo del corpus de FastAPI) → escaneo limpio.
- `.env.example` — añadidas `ENVIRONMENT` y `CORS_ORIGINS` como opcionales documentadas.
- `docs/release/v1.0.0.md` — mensaje del tag anotado `v1.0.0` + cuerpo del release (preparados; tag y publicación son gate humano).
- **fix(scripts):** `docker-compose.yml` monta `./scripts:/app/scripts:ro` — la verificación desde clone fresco reveló que los comandos documentados `docker compose exec backend python scripts/<x>.py` fallaban (scripts/ no estaba montado). README corregido con los comandos verificados.
- **Verificación end-to-end desde clone fresco** (`down -v` → up → indexar → 5 turnos con citas → /eval PASS → /redteam 20/20 → 331 spans en Phoenix → PR de regresión bloqueado por CI). Detalle en `SESSION.md`. 279 tests verdes, ruff limpio, gitleaks sin hallazgos.

### Añadido (Bloque S — Seguridad: defensa en profundidad en 5 capas)

- `backend/app/security/` — módulo nuevo con las 5 capas (spec 09, OWASP LLM01/LLM02):
  - `models.py` — `BlockingLayer` (enum 1..5 con la capa que cortó), `Verdict`, `GuardrailVerdict` (con `blocked`/`flagged`/`failed_open`), `OutputScanResult`.
  - `safety.py` (**capa 1**) — `default_safety_settings()` con `BLOCK_MEDIUM_AND_ABOVE` en HARASSMENT/HATE_SPEECH/SEXUALLY_EXPLICIT/DANGEROUS_CONTENT; `is_safety_block(finish_reason)`. Categorías de imagen/civic-integrity excluidas para no penalizar preguntas técnicas de seguridad.
  - `guardrail.py` (**capa 2**) — `InputGuardrail` sobre Gemini Flash; clasifica el input en legitimate/suspicious/hostile; parser de JSON tolerante a fences; **fail-open** a legitimate ante cualquier error (disponibilidad sobre estrictez; las capas profundas siguen aplicando).
  - `output_filter.py` (**capa 4**) — regex PII (email, tarjeta con checksum Luhn, IPv4/IPv6) → placeholders; `StreamRedactor` con holdback de 80 chars que nunca corta un match en el borde de emisión (redacción correcta sobre streaming SSE); `detect_system_prompt_leak()` por firmas del system prompt.
  - `incidents.py` (**capa 5**) — `log_incident()` emite span `security_incident` con `blocking_layer`/`blocking_layer_name`/`blocked`; solo un fingerprint SHA-256 del query (PII nunca se loguea); `SAFE_RESPONSE` genérico (sin oráculo para el atacante).
  - `rate_limit.py` (**capa 5**) — `check_rate_limit(user_id)` con `limits` (MovingWindow en memoria), 30 req/min por usuario configurable.
- `prompts/guardrail.md` — prompt v1.0 del clasificador de la capa 2 (modelo de amenazas, criterios, salida JSON, input delimitado como datos no confiables).
- `security/red-team-checklist.md` — 20 prompts hostiles (16 directos + 4 injection indirecta) + 3 controles legítimos; mapeo OWASP; criterios de evaluación por tipo.
- `scripts/red_team.py` — harness que corre la checklist contra el sistema real: autentica, envía cada caso a `/chat`, **planta chunks envenenados en pgvector para la injection indirecta** (los embebe con `RETRIEVAL_DOCUMENT`, lanza una query benigna que los recupera, verifica que el modelo no obedece, y los borra), reintenta una vez ante respuesta vacía/error transitoria, y reporta block rate + `security/red-team-results.md`. Flags `--no-indirect`, `--dry-run`.
- `backend/tests/security/` — `test_output_filter.py` (redaction, Luhn, holdback en streaming, leak), `test_guardrail.py` (parser, verdicts, fail-open), `test_safety_and_incidents.py` (safety settings, fingerprint, rate limit por usuario).

### Cambiado (Bloque S)

- `backend/app/chat/generator.py` — `safety_settings` en `ChatGoogleGenerativeAI` (capa 1); captura de `finish_reason` por chunk; flag `safety_blocked` en `StreamingSession` cuando Gemini bloquea.
- `backend/app/chat/router.py` — guardrail pre-retrieval (hostile → `_safe_response()` sin tocar el corpus ni el modelo, suspicious → flag en el span); redaction PII del stream con `StreamRedactor`; detección de leak post-stream; **se persiste el texto redactado** (PII nunca llega al historial); `rate_limited_user` enforce 30/min y registra incidente al exceder. La dependencia de autenticación se declara **primero** en el endpoint: FastAPI resuelve los `Depends` en orden y los adapters de Gemini construyen su cliente de forma eager (sin API key revientan), así que auth debe resolverse antes para devolver 401/429 limpios en vez de 500.
- `backend/app/main.py` — el rate limiting se aplica vía dependencia, no vía middleware: `SlowAPIMiddleware` es un `BaseHTTPMiddleware` que rompía el manejo temprano del 401.
- `prompts/system.md` v1.3 — sección de seguridad (capa 3): el `<context>` es dato no confiable, no obedecer instrucciones embebidas, no revelar el system prompt/configuración, no cambiar de rol, no emitir secretos/PII.
- `backend/app/chat/prompts.py` — el bloque de contexto se envuelve en `<context>…</context>` con aviso explícito de dato no confiable.
- `.claude/commands/redteam.md` — el skill `/redteam` ejecuta `scripts/red_team.py` y cruza resultados con los spans `security_incident` de Phoenix por capa.
- `backend/pyproject.toml` — añadida dep `slowapi>=0.1.9` (se usa su transitiva `limits`); `backend/app/config.py` — settings `guardrail_timeout_s`, `rate_limit_per_minute`, `security_guardrail_enabled`.

### Notas (Bloque S)

- **279 tests, todos verdes. Ruff limpio.**
- **Red team contra el sistema real: block rate 20/20** (gate ≥18/20), **4/4 injection indirecta** neutralizada, **3/3 controles** respondidos sin falso positivo, 0 fugas de PII/system prompt. Incidentes con `blocking_layer` verificados en Phoenix (GUARDRAIL + OUTPUT_FILTER).
- El guardrail (LLM Flash) tiene varianza y el free-tier devuelve respuestas vacías/error transitorias; el harness reintenta una vez. Aunque el guardrail dejara pasar un caso, la capa 3 (system prompt) también rechaza (defensa en profundidad real).
- Rate limiting en memoria (single-worker). Para multi-worker: `RedisStorage`. PII más allá del regex (p. ej. Presidio): evolución para v1.1, no implementado.

### Añadido (Bloque F — Observabilidad consolidada)

- `backend/app/observability/cost.py` — `QueryCost` dataclass + `compute_cost(usage, model)` con pricing Gemini anclado 2026-05-20. Flash: $0.30 input / $0.075 cached / $1.25 output por millón de tokens. Pro: $1.25 / $0.3125 / $5.00. Modelos desconocidos degradan a Flash. Expone `savings_usd`, `cache_hit_rate`, `caching_available`.
- `backend/app/chat/router.py` — span `chat_turn` manual (inicia antes del retrieval, propaga contexto OTel via `otel_context.attach/detach` para que `asyncio.to_thread` copie el contexto a los sub-spans) + span `generate` manual dentro de `event_generator()` como hijo de `chat_turn` via `set_span_in_context`. Atributos del span `generate`: `prompt_tokens`, `cached_tokens`, `output_tokens`, `total_tokens`, `ttft_ms`, `caching_available`, `cache_hit_rate`, `cost_usd`, `input_usd`, `cached_usd`, `output_usd`, `savings_usd`. Atributos del span `chat_turn`: `total_latency_ms`, `turn_idx`, `total_cost_usd`, tokens. Cierra el TODO de bloque CH sobre el span del generador.
- `docs/cost-model.md` — tabla de precios Gemini con versión y fecha, desglose por turno (rewriter + reranker + generador), impacto del caching implícito, proyección mensual (ligero/moderado/demo).
- `infra/phoenix/dashboards/health.json` — 8 paneles: latencia total p50/p95/p99, TTFT, latencia rerank/rewrite, tasa de fallback del reranker, throughput, tasa de errores, candidatos dense/sparse. Alertas configuradas.
- `infra/phoenix/dashboards/quality.json` — 8 paneles: 4 métricas RAGAS con baseline y floor, recall@5/MRR del gate, abstention rate, metadatos del run (subset/SHA), regresión vs baseline.
- `infra/phoenix/dashboards/cost.json` — 8 paneles: coste por turno, tokens por categoría, cache hit rate, ahorro acumulado, desglose pie, coste 24h, top sesiones por consumo, disponibilidad del caching.
- `scripts/measure_caching_impact.py` — autentica contra el backend, envía N turnos SSE en la misma sesión, recupera atributos del span `generate` desde Phoenix REST API, calcula cache hit rate / ahorro / TTFT y escribe `docs/caching-impact.md`. Flags: `--turns`, `--dry-run`, `--no-write`, `--output`.
- `docs/caching-impact.md` — metodología, limitación conocida (Issue #12: LangChain `astream()` no expone `usage_metadata` en streaming, por lo que `cached_content_token_count` puede ser 0 aunque el caching esté activo), estimación teórica (5 turnos), instrucciones de actualización con stack real.
- `.claude/commands/dashboard.md` — actualizado: verifica Phoenix en `:6006`, consulta `GET /v1/spans`, computa métricas de salud/coste/calidad, renderiza tabla con emojis de alerta (✅/⚠️/❌), destaca fases lentas, apunta a los 3 ficheros de definición de dashboards.
- `backend/tests/observability/test_cost.py` — 23 tests: aritmética (zero tokens, sin caché, con caché, clamping cached > prompt), Pro vs Flash, fallback de modelo desconocido, `compute_cost()`, funciones utilitarias, turno realista.
- `specs/12-observability-block-f.md` — spec del bloque.

### Cambiado (Bloque F)
- `backend/app/chat/router.py` — añadidos `import time`, `otel_context`, `set_span_in_context`, `otel_trace`, `compute_cost`. Eliminado import no usado de `set_span_attributes`. El `TODO(block-F)` sobre el span del generador queda resuelto.

### Notas (Bloque F)
- **249 tests, todos verdes. Ruff limpio.**
- Los dashboards JSON en `infra/phoenix/dashboards/` son **especificaciones de paneles** — Phoenix self-hosted no tiene endpoint REST de importación de dashboards. Se usan como referencia para crear los paneles manualmente en la UI de Phoenix y como fuente de verdad para el skill `/dashboard`.
- La medición real de `docs/caching-impact.md` (con `GOOGLE_API_KEY` y stack levantado) es el único pendiente del gate humano, junto con la verificación visual del árbol de spans en Phoenix.

---

### Gate humano — fixes y decisiones (Bloque E, sesión 10)
- **fix(retrieval):** el LLM-reranker (y el rewriter) caían **siempre** al fallback por drift de la API de Gemini (deadline mínimo 10s; spec 03 usaba 5s/1.5s). Reranker recortado a 8 candidatos, `rerank_timeout_s` 15s, `rewrite_timeout_s` 10s, `max_retries=0` (un 504 degradaba a ~2min por reintentos). Medido: p50 10.0s / p95 10.9s, 0/7 fallbacks.
- **fix(chat):** prompt de generación v1.2 fuerza respuesta en español (respondía en inglés en parte de los turnos). faithfulness 0.84→0.95 tras el fix.
- **fix(evals):** detector de abstención reconoce marcadores en inglés (sigue siendo frágil; flag estructurado pendiente para v1.1); `gemini_pro_model` corregido a `gemini-3-pro-preview` (el id sin sufijo daba 404); juez timeout 120→300s.
- **refactor(evals):** el gate bloquea solo sobre las 4 métricas del juez; recall@5/MRR pasan a advisory (el match determinista por `(source, section)` es demasiado estricto para multi_source).
- **feat(evals):** floors del juez (faithfulness 0.80, answer_relevancy 0.70, context_precision 0.80, context_recall 0.85) + regresión **absoluta** (>0.07 vs baseline). `baseline_metrics.json` pinneado sobre `ci_subset` (faith 0.945 / ar 0.846 / cp 0.987 / cr 0.958).
- **ci(evals) — gate del PR DETERMINISTA, juez LLM en la nocturna:** el juez Gemini 3 Pro (~50 s/llamada) + latencia/varianza/cuota del free-tier lo hacen inviable como bloqueante por-PR (el `ci_subset` se iba a ~13-14 min; con cuota agotada los runs del juez expiraban, 1/20 trabajos en 11 min). Por eso:
  - **`eval.yml` (gate del PR, bloqueante):** solo deterministas — `recall@5`/`MRR` sobre los answerable label-matchables de `CI_GATE_IDS` (6 ej.), excluyendo multi_source (g-24) y no_se (g-31). Sin generación ni juez → corre en segundos (verificado: sano 70 s PASS, retrieval roto 7 s FAIL). Floors recall@5/MRR ≥ 0.85. Caché de índice con `actions/cache`; Azurite vía `docker run --skipApiVersionCheck`; `timeout-minutes: 8`.
  - **`eval-nightly.yml` (monitor de tendencia, NO bloquea PRs):** RAGAS + Gemini Pro sobre los 40, floors del juez + regresión absoluta 0.07 vs baseline, refresca `baseline_metrics.json`. Un run rojo es alerta de tendencia.
  - `report.py`: `evaluate_gate` (determinista) + `evaluate_judge` (monitor). `runner.run_evals` admite `use_generator=False` (retrieval-only) y excluye multi_source del recall determinista. CLI: `--retrieval-only`.
  - Branch protection en `main` con el check `Eval gate (ci_subset)` + secret `GOOGLE_API_KEY`.

### Añadido (Bloque E — Evaluación + CI con gate del PR)
- `backend/app/evals/` — módulo de evaluación (spec 10 / ADR-007):
  - `loader.py` — carga `gold.jsonl` (40 ej.) en `GoldExample` (normaliza claves `_es` → modelo inglés); `CI_SUBSET_IDS` (15 ej. representativos, cubre los 5 tipos) y `select_subset` (falla si falta un id).
  - `metrics.py` — métricas deterministas sin LLM: `recall_at_k`, `reciprocal_rank` (match por `(source, section)`), `is_abstention` (detección de rechazo para `no_se`).
  - `runner.py` — `run_evals`: retrieve → generate por ejemplo, agrega recall@5/MRR (answerable), abstention_rate (`no_se`) y las 4 métricas RAGAS (juez, answerable). Captura errores por-ejemplo sin abortar.
  - `judge.py` — `RagasGeminiJudge`: RAGAS con Gemini Pro como juez (faithfulness, answer_relevancy, context_precision, context_recall); `RunConfig` con `max_workers` para el free tier; import de `ragas` diferido; NaNs excluidos de la media.
  - `generator.py` — `GeminiAnswerGenerator`: respuesta completa (no streaming) con Gemini Flash, reusando `build_prompt`.
  - `ports.py` — `AnswerGeneratorPort`, `JudgePort` (ADR-011, mockeables en tests).
  - `report.py` — `evaluate_gate` (floor absoluto + regresión relativa opcional vs baseline de `main`), `render_markdown` (tabla del comentario del PR), `report_to_baseline`.
  - `thresholds.yaml` — floors orientativos (provisionales hasta el gate humano) + config de regresión.
  - `telemetry.py` — `record_eval_run`: span Phoenix `evals.run` con métricas, subset, commit/corpus SHA (dashboard de Calidad).
  - `cli.py` — `python -m app.evals.cli` (`--subset ci_subset|full`, `--baseline`, `--update-baseline`, `--markdown`, `--json`, `--no-judge`); exit 0/1/2.
- `backend/tests/evals/` — 71 tests (loader, métricas, runner con fakes, gate/report, pipeline parametrizado sobre el gold con marker `ci_subset`).
- `.github/workflows/eval.yml` — gate del PR: Postgres + Azurite como services, indexa el corpus, corre el subset `ci_subset`, comenta el PR con la tabla y bloquea el merge si falla. Guard que se salta limpio si falta `GOOGLE_API_KEY`.
- `.github/workflows/eval-nightly.yml` — suite completa (40 ej.) en `schedule` + `workflow_dispatch`; refresca `baseline_metrics.json` en `main`.

### Cambiado (Bloque E)
- `backend/app/config.py` — `gemini_pro_model` (juez), `evals_judge_max_workers`, `evals_judge_timeout_s`, `evals_gen_timeout_s`.
- `backend/pyproject.toml` — deps `ragas>=0.2,<0.3` y `pyyaml`; markers `ci_subset` y `evals_live`.
- `.claude/commands/eval.md` — el slash `/eval` ahora invoca el runner (`app.evals.cli`).

> **Gate humano pendiente** antes de cablear CI a producción: medir baseline sobre `main`, acordar la estrategia del gate y validar el juez (ver SESSION.md). Los thresholds de `thresholds.yaml` son provisionales hasta entonces.

---

## [Bloque D — Frontend chat completo] — 2026-05-22

### Corregido (review fixes)
- **Citations scoping por mensaje** (`Message.tsx`, `MessageList.tsx`, `ChatPage.tsx`): la firma de `onCitationClick` pasa ahora `(index, citations)` — el array de citas del mensaje pulsado. `ChatPage.handleCitationClick` usa ese array directamente para abrir `CitationsPanel`; eliminados `findLastCitations` y el `useEffect` de sincronización. En conversaciones multi-turno, cada chip `[N]` abre las fuentes de su propio turno. Verificado en vivo con 2 turnos con sources distintos.
- **DOM event bus eliminado** (`CitationsPanel.tsx`, `ChatPage.tsx`): la navegación entre citas dentro del panel usaba `document.dispatchEvent(CustomEvent)` con `document.addEventListener` en el padre — anti-patrón React. Reemplazado por la prop `onSelectIndex: (i: number) => void` que `ChatPage` pasa como `setSelectedCitationIndex`.

### Añadido
- `specs/11-frontend-chat.md` — spec del bloque D (frontend de chat): hook SSE, componentes, CitationsPanel, SessionSelector, build prod nginx, XSS, checklist de verificación.
- `frontend/src/index.css` — design system completo: variables CSS (`--bg`, `--fg`, `--accent`, `--highlight`, `--muted`, `--green`, `--danger`, `--orange`); familia tipográfica Poppins (UI) y JetBrains Mono (código); estilos de prosa `.prose` (pre, code, blockquote, table, listas, headings); clase `.citation-chip` (verde `--highlight`, monoespaciada); cursor `.streaming-cursor` (naranja parpadeante); `@keyframes spin` para spinner de envío.
- `Makefile` — `make dev` (Vite :5173), `make prod` (nginx :80 vía perfil `prod`), `make down`.
- `frontend/src/api/chat.ts` — tipos `Citation`, `SessionOut`, `MessageOut`, `SessionDetailOut`; funciones `listSessions()` (`GET /chat/sessions`) y `getSession(id)` (`GET /chat/sessions/{id}`); `credentials: "include"` en todas las llamadas.
- `frontend/src/hooks/useChatStream.ts` — hook `useChatStream`: consume `POST /chat/` como SSE vía `fetch` + `ReadableStream`; parsea líneas `data: <json>` del formato sse_starlette; gestiona `AbortController` (cancela al desmontar o al iniciar nueva petición); callbacks `onToken(text)`, `onCitations(citations)`, `onDone()`; expone `streaming`, `error`, `sendMessage`, `cancel`.
- `frontend/src/components/ChatInput.tsx` — textarea + botón enviar con icono SVG; `Enter` envía, `Shift+Enter` inserta salto; deshabilitado (aria-disabled) durante streaming; spinner animado en botón; label `sr-only`; focus visible en todos los interactivos.
- `frontend/src/components/MessageList.tsx` — lista scrollable con `role="log"` y `aria-live="polite"`; auto-scroll al bottom (`scrollIntoView`) en cada cambio de mensajes; estado vacío con texto orientativo; indicador de loading (tres puntos naranja animados) mientras espera el primer token.
- `frontend/src/components/Message.tsx` — burbujas de chat: usuario (derecha, `#eef6f3`, `pre-wrap`) y asistente (izquierda, fondo transparente); render markdown con `ReactMarkdown` + `remark-gfm` + `rehype-sanitize` (XSS); cuando `citations` está presente y no hay streaming activo, `[N]` en el texto se transforman en `.citation-chip` clicables via `renderWithCitationChips`; cursor naranja durante streaming.
- `frontend/src/components/CitationsPanel.tsx` — panel deslizante fijo (lado derecho, `min(420px, 100vw)`); muestra número de cita, sección, URL fuente (enlace externo) y hash truncado; lista de todas las citas con resaltado de la activa; cierre con botón ✕, clic en backdrop o tecla Escape; `role="complementary"`, `aria-label`; auto-foco en apertura; `select-citation` custom event para navegación interna.
- `frontend/src/components/SessionSelector.tsx` — sidebar izquierda (220 px); carga `GET /chat/sessions` en mount y ante incremento de `refreshTrigger`; ordena por `updated_at` desc; botón "Nueva conversación"; sesión activa con `aria-current`; estados de carga, error y vacío.
- `frontend/nginx.conf` — servidor nginx para build de producción: `try_files` para SPA; `location /api/` proxied a `http://backend:8000/` con strip del prefijo; `proxy_buffering off` + `proxy_http_version 1.1` para SSE token-a-token sin acumulación de buffer.
- `frontend/Dockerfile.prod` — build multi-stage: etapa `node:22-alpine` con `npm ci` + `npm run build` (`VITE_API_URL=/api`); etapa `nginx:1.27-alpine` que sirve `dist/` y usa `nginx.conf`. Puerto 80.

### Cambiado
- `frontend/src/pages/ChatPage.tsx` — reescritura completa: cabecera con badge RAG + email + botón salir; layout flex con `SessionSelector` (sidebar) + `MessageList` + `ChatInput`; panel `CitationsPanel` superpuesto; gestión de `currentSessionId` con `crypto.randomUUID()` client-side (idempotente en backend); `refreshTrigger` incremental post-turno; `loadSession` reconstruye el array de mensajes desde `GET /chat/sessions/{id}`; indicador de error SSE en header; escucha `select-citation` DOM event.
- `frontend/index.html` — añadidas `<link>` para Google Fonts: Poppins (400/500/600) y JetBrains Mono (400/500) con `preconnect` + `display=swap`.
- `frontend/src/main.tsx` — importa `./index.css`.
- `frontend/package.json` + `package-lock.json` — nuevas dependencias de producción: `react-markdown@^9.1.0`, `rehype-sanitize@^6.0.0`, `remark-gfm@^4.0.1`.
- `docker-compose.yml` — servicio `frontend-prod` (puerto `80:80`, `Dockerfile.prod`, `profiles: [prod]`); el servicio `frontend` existente (dev) no cambia.

### Decisiones documentadas
- **SSE via `fetch` + `ReadableStream`**: `EventSource` sólo soporta GET. `POST /chat/` necesita body JSON, por lo que se lee el stream de bytes directamente y se parsean líneas `data:`. `AbortController` garantiza la cancelación en desmontaje.
- **UUID de sesión client-side**: El backend acepta `session_id: UUID | None`; si el UUID no existe, lo crea (idempotente por `ON CONFLICT DO NOTHING`). El frontend genera el UUID con `crypto.randomUUID()` para conocer el `session_id` desde el primer turno sin añadir campo a la respuesta SSE.
- **`rehype-sanitize` con schema por defecto**: Schema verificado programáticamente: `<script>` ausente de `tagNames`, sin atributos `on*` en wildcards. Protege contra XSS de chunks del corpus incluidos en respuestas del modelo.
- **Citation chips via split de texto**: `renderWithCitationChips` divide la cadena markdown en `[N]` (botones) y fragmentos de prosa (ReactMarkdown con `p → <>{children}</>`). Evita remark plugins custom sin perder la render correcta de markdown.
- **`refreshTrigger` prop para re-fetch de sesiones**: Contador incrementado tras `onCitations` y `onDone` que dispara `useEffect` en `SessionSelector`. Simple, sin Context global ni polling.
- **Perfil `prod` separado en docker-compose**: `frontend-prod` con `profiles: [prod]` no interfiere con el stack dev por defecto. Se activa con `docker compose --profile prod up`.

### Notas
- **147 tests backend, todos verdes. Ruff limpio. TypeScript sin errores** (`tsc --noEmit`).
- **Build de producción verificado**: 311 módulos transformados, 365 KB JS (gzip 115 KB), CSS 2.3 KB.
- **SSE verificado en vivo**: `curl -N` con cookie → stream `token` × N + evento `citations` final.
- **Sanitización XSS verificada** con la librería directamente (node): `<script>` y `on*` fuera del schema por defecto.
- **Sin tests automáticos de frontend** en v1.0 (deuda registrada en spec 11, riesgo documentado).
- **Checklist visual para Javi**: 10 puntos en `SESSION.md` (flujo register→chat→multi-turno→sesiones persistentes→prod→logout).

---

## [Bloque AU] — 2026-05-22

### Añadido
- `backend/migrations/versions/0003_create_users_add_fk.py` — tabla `users` (id UUID PK, email VARCHAR(320) UNIQUE, hashed_password, is_active, is_superuser, is_verified); `CREATE UNIQUE INDEX ix_users_email`; FK `chat_sessions.user_id → users.id ON DELETE SET NULL` (revision 0003, down_revision 0002). Migración ejecutada contra stack Docker real.
- `backend/app/auth/` — módulo de autenticación completo (ADR-006):
  - `models.py`: `User(SQLAlchemyBaseUserTableUUID, Base)` con `__tablename__ = "users"`.
  - `schema.py`: `UserRead`, `UserCreate`, `UserUpdate` (FastAPI Users Pydantic schemas, UUID id).
  - `db.py`: async engine singleton (`create_async_engine` + `async_sessionmaker`, psycopg v3) sobre el mismo `database_url`; `get_async_session`; `get_user_db → SQLAlchemyUserDatabase`. Coexiste con el engine sync de chat/retrieval.
  - `manager.py`: `UserManager(UUIDIDMixin, BaseUserManager)` con `on_after_register`/`on_after_login`.
  - `router.py`: `access_backend` (cookie `access_token`, httpOnly, SameSite=Lax, TTL 1 h) + `refresh_backend` (cookie `refresh_token`, TTL 7 d). `cookie_secure` según entorno. `FastAPIUsers` + `current_active_user`. Rutas: `POST /auth/register`, `POST /auth/login|logout`, `POST /auth/refresh/login|logout`, `GET /auth/me`, `PATCH /auth/me`.
- `backend/tests/auth/test_auth.py` — 10 tests: guards 401 para los tres endpoints de chat sin cookie; scoping 403 (sesión ajena) y 200 (sesión propia); filtrado de lista por usuario; existencia de rutas auth.
- `frontend/src/api/auth.ts` — `register`, `login` (form-encoded OAuth2 `username=`), `logout`, `getMe`; `credentials: "include"` en todas las llamadas.
- `frontend/src/hooks/useAuth.tsx` — `AuthProvider` + `useAuth`; rehydrata desde cookie en mount; expone `user`, `loading`, `login`, `register`, `logout`.
- `frontend/src/components/ProtectedRoute.tsx` — redirige a `/login` mientras carga o si `user === null`.
- `frontend/src/pages/Login.tsx` — formulario email/password → `POST /auth/login` → redirect `/`.
- `frontend/src/pages/Register.tsx` — formulario email/password/confirm → `POST /auth/register` + auto-login → redirect `/`.
- `frontend/src/pages/ChatPage.tsx` — página protegida con cabecera (email + logout); placeholder de chat (bloque FE).

### Cambiado
- `backend/app/config.py` — `jwt_access_ttl_s = 3600` (1 h); `jwt_refresh_ttl_s = 604800` (7 d); `model_validator` que lanza `ValidationError` si `environment != "development"` y `jwt_secret == "change-me"`; propiedad `cookie_secure` (True si environment != development).
- `backend/app/main.py` — `CORSMiddleware` (`allow_origins=["http://localhost:5173"]`, `allow_credentials=True`); incluye `auth_router`.
- `backend/app/chat/store.py` — `get_or_create_session(session_id, user_id=None)` inserta `user_id`; `list_sessions(user_id=None)` filtra por usuario; **`save_turn` refactorizado**: adquiere `pg_advisory_xact_lock(hashtext(session_id))`, recomputa `turn_idx` dentro de la misma transacción bloqueada (cierra la carrera TOCTOU de bloque CH), devuelve el índice escrito; firma sin parámetro `turn_idx` externo.
- `backend/app/chat/router.py` — tres endpoints protegidos con `Depends(current_active_user)`; POST /chat pasa `user_id=current_user.id`; GET /sessions filtra por `user_id`; GET /sessions/{id} devuelve 403 si `session.user_id != current_user.id`; usa `turn_idx_hint` para log pre-stream; `turn_idx` authoritative devuelto por `save_turn`.
- `backend/pyproject.toml` + `uv.lock` — `fastapi-users[sqlalchemy]>=13.0` (instalada 15.0.5).
- `backend/tests/chat/conftest.py` — `FakeChatHistoryStore`: `get_or_create_session(user_id=None)` guarda user_id; `list_sessions(user_id=None)` filtra; `save_turn` computa turn_idx internamente y lo devuelve.
- `backend/tests/chat/test_router.py` — fixture `client` inyecta `current_active_user` con `fake_user` vía dependency override.
- `backend/tests/chat/test_store.py` — `TestSaveTurn` actualizado a nueva firma (sin `turn_idx` explícito, verifica el retorno).
- `frontend/src/App.tsx` — reescrito con `BrowserRouter` + `AuthProvider`; rutas públicas `/login|/register`; ruta protegida `/` bajo `ProtectedRoute`.
- `frontend/package.json` — dep `react-router-dom ^7`.
- `frontend/tsconfig.node.json` — `noEmit: false` (corrección: `composite: true` + `noEmit: true` es inválido para referenced projects).

### Decisiones documentadas
- **Async engine separado**: psycopg v3 soporta `create_async_engine` con el mismo `database_url`. El engine sync no se toca; el async sólo lo usa `app/auth/db.py`.
- **`cookie_secure` según entorno**: dev → sin `Secure` (permite HTTP localhost); prod → `Secure` (HTTPS obligatorio). Controlado por `Settings.cookie_secure` derivado de `environment`.
- **`__tablename__ = "users"`**: `SQLAlchemyBaseUserTableUUID` no fija nombre; SQLAlchemy defaultearía a `user`, reservada en Postgres.
- **Login form-encoded**: FastAPI Users `CookieTransport` usa `OAuth2PasswordRequestForm` (campo `username`). Frontend envía `application/x-www-form-urlencoded`.
- **JWT_SECRET obligatorio en producción**: `model_validator(mode="after")` valida `jwt_secret != "change-me"` cuando `environment != "development"`. Fallo al arrancar, no en runtime.
- **Carrera `next_turn_idx` cerrada**: `save_turn` adquiere advisory lock al inicio de la transacción → lee MAX → inserta, todo atómico. `next_turn_idx` público se mantiene para estimaciones pre-stream (sin lock). UNIQUE constraint sigue como last-resort guard.

### Notas
- **145 tests, todos verdes. Ruff limpio. TypeScript sin errores** (`npx tsc --noEmit`).
- **Verificación live completa** contra stack Docker real:
  - Register (201) → Login (204, cookie `HttpOnly; Max-Age=3600; SameSite=lax`) → GET /me (200, sin `hashed_password`) → GET /chat/sessions (200, filtrado por usuario) → Logout (204, `Max-Age=0`) → POST /chat post-logout (401). CORS: `access-control-allow-credentials: true`.
  - Scoping: `GET /chat/sessions/<sesión de B>` con cookie de A → 403.
  - Refresh cookie: `refresh_token; Max-Age=604800; HttpOnly; SameSite=lax`.
  - JWT_SECRET en production sin variable → `ValidationError` al cargar Settings.
  - `pg_advisory_xact_lock` disponible y funcional en Postgres 17.

---

## [Bloque AU] — 2026-05-22

### Añadido
- `backend/migrations/versions/0003_create_users_add_fk.py` — tabla `users` (id UUID PK, email UNIQUE, hashed_password, is_active, is_superuser, is_verified) + `CREATE UNIQUE INDEX ix_users_email`. FK `chat_sessions.user_id → users.id ON DELETE SET NULL`.
- `backend/app/auth/` — módulo de autenticación completo (ADR-006):
  - `models.py`: `User(SQLAlchemyBaseUserTableUUID, Base)` con `__tablename__ = "users"`.
  - `schema.py`: `UserRead`, `UserCreate`, `UserUpdate` (FastAPI Users Pydantic schemas, UUID id).
  - `db.py`: async engine singleton (`create_async_engine` + `async_sessionmaker`) sobre el mismo `database_url`; `get_async_session`; `get_user_db → SQLAlchemyUserDatabase`. Coexiste con el engine sync de chat/retrieval.
  - `manager.py`: `UserManager(UUIDIDMixin, BaseUserManager)` con hooks `on_after_register` / `on_after_login`. Secrets leídos de `get_settings()` cached.
  - `router.py`: dos `AuthenticationBackend` — `access_backend` (cookie `access_token`, httpOnly, SameSite=Lax, TTL 1 h) + `refresh_backend` (cookie `refresh_token`, httpOnly, SameSite=Lax, TTL 7 d). `FastAPIUsers` instance + `current_active_user`. Rutas: `POST /auth/register`, `POST /auth/login|logout`, `POST /auth/refresh/login|logout`, `GET /auth/me`, `PATCH /auth/me`.
- `backend/tests/auth/test_auth.py` — 10 tests: guards 401 para `POST /chat/`, `GET /chat/sessions`, `GET /chat/sessions/{id}`; scoping 403 (sesión ajena) y 200 (sesión propia); filtrado lista; existencia de rutas auth.
- `frontend/src/api/auth.ts` — funciones `register`, `login` (form-encoded OAuth2 `username=`), `logout`, `getMe`; `credentials: "include"` en todas las llamadas.
- `frontend/src/hooks/useAuth.tsx` — `AuthProvider` + `useAuth`; rehydrata desde cookie en mount (`getMe`); expone `user`, `loading`, `login`, `register`, `logout`.
- `frontend/src/components/ProtectedRoute.tsx` — redirige a `/login` mientras carga o si `user === null`.
- `frontend/src/pages/Login.tsx` — formulario email/password, `POST /auth/login`, redirect `/`.
- `frontend/src/pages/Register.tsx` — formulario email/password/confirm, `POST /auth/register` + auto-login, redirect `/`.
- `frontend/src/pages/ChatPage.tsx` — ruta protegida con cabecera (email del usuario + botón logout); placeholder del chat (bloque FE).

### Cambiado
- `backend/app/config.py` — añadidos `jwt_access_ttl_s = 3600` (1 h) y `jwt_refresh_ttl_s = 604800` (7 d).
- `backend/app/main.py` — `CORSMiddleware` (`allow_origins=["http://localhost:5173"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`); incluye `auth_router`.
- `backend/app/chat/store.py` — `get_or_create_session(session_id, user_id=None)` inserta `user_id` en la fila nueva; `list_sessions(user_id=None)` filtra por `user_id` cuando se pasa.
- `backend/app/chat/router.py` — `POST /chat/`, `GET /chat/sessions`, `GET /chat/sessions/{id}` protegidos con `current_user: User = Depends(current_active_user)`. `POST /chat/` pasa `user_id=current_user.id`. `GET /chat/sessions` filtra por `user_id`. `GET /chat/sessions/{id}` devuelve 403 si `session.user_id != current_user.id`.
- `backend/pyproject.toml` + `uv.lock` — dep `fastapi-users[sqlalchemy]>=13.0` (instalada 15.0.5).
- `backend/tests/chat/conftest.py` — `FakeChatHistoryStore.get_or_create_session(user_id=None)` guarda `user_id`; `FakeChatHistoryStore.list_sessions(user_id=None)` filtra.
- `backend/tests/chat/test_router.py` — fixture `client` inyecta `current_active_user` con `fake_user` (MagicMock con UUID).
- `frontend/src/App.tsx` — reescrito con `BrowserRouter` + `AuthProvider`; rutas públicas `/login` `/register`; ruta protegida `/` bajo `ProtectedRoute`.
- `frontend/package.json` — dep `react-router-dom ^7`.
- `frontend/tsconfig.node.json` — `noEmit: false` (corrección: `composite: true` + `noEmit: true` no es válido para referenced projects).

### Decisiones documentadas
- **Async engine separado para FastAPI Users**: psycopg v3 soporta `create_async_engine` con el mismo prefijo `postgresql+psycopg://`. El engine sync de chat/retrieval no se toca; el async solo lo usa `app/auth/db.py`.
- **Dos cookies httpOnly (ADR-006)**: `access_token` (1 h) para requests API + `refresh_token` (7 d) para renovar sin re-login. Ambas con SameSite=Lax.
- **`__tablename__ = "users"`**: `SQLAlchemyBaseUserTableUUID` no fija nombre; SQLAlchemy defaultearía a `user` (palabra reservada en Postgres). Override explícito.
- **Login form-encoded**: FastAPI Users `get_auth_router` con `CookieTransport` usa `OAuth2PasswordRequestForm` (campo `username`). Frontend envía `application/x-www-form-urlencoded`.
- **Stubs de retrieval en tests de guard 401**: FastAPI resuelve todas las deps antes de rechazar por auth; sin stubs de Gemini el test daría 500. Se añaden `_setup_retrieval_stubs()` en los tests de guard.

### Notas
- **145 tests, todos verdes**. Ruff limpio. TypeScript `noEmit` limpio.
- Verificación live (register/login/logout por UI contra stack Docker): pendiente de gate humano.

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
