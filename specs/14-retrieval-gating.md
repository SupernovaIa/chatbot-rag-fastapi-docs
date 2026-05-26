# Spec 14 · Retrieval gating

**Estado:** aceptada
**Bloque:** EV2 (Evolutivo post-1.0 — cierre v1.2.0)
**Dependencias:** Spec 05 (chat endpoint), Spec 06 (gestión de historial), Spec 09 (capas de seguridad — capa 2 guardrail), ADR-011 (arquitectura de código), **ADR-013 (retrieval gating)**.

## Goal

Decidir, antes del pipeline `rewrite → retrieve → rerank`, si la consulta necesita recuperar contexto del corpus. Para saludos, agradecimientos, meta-preguntas sobre la propia conversación y follow-ups resolubles con el historial, **saltar retrieval** y responder directo. Objetivo medible: bajar latencia y coste por turno en los casos sin retrieval **sin que las evals de calidad regresen**.

## User story

> Como usuario, cuando saludo, agradezco o hago una pregunta sobre la conversación, quiero una respuesta rápida y directa, sin que el sistema gaste tiempo y cuota buscando en la documentación; y cuando hago una pregunta técnica, quiero que sí busque y cite.

## Approach

- [ ] **Modelo:** `IntentVerdict` (dataclass) en `backend/app/chat/intent.py`: `needs_retrieval: bool`, `reason: str`, `failed_open: bool = False`.
- [ ] **Puerto fino + adaptador (`IntentGate`)** en `backend/app/chat/intent.py`, espejo de `InputGuardrail` (spec 09): recibe un `ChatLLMPort` (ya existe en `app.retrieval.ports`), método `classify(query, history) -> IntentVerdict`. Prompt versionado en `prompts/intent_gate.md`, cargado con stripping de front-matter y cacheado (mismo patrón que `guardrail.py`). Parser JSON tolerante a fences/prosa. **Fail-open hacia retrieve**: cualquier error (timeout, parseo, API caída) → `IntentVerdict(needs_retrieval=True, failed_open=True)`. El prompt se sesga a `needs_retrieval=true` ante ambigüedad (el falso salto es el fallo caro).
- [ ] **Prompt `prompts/intent_gate.md`** v1.0: define la tarea (clasificar si el turno necesita documentación de FastAPI), las categorías que saltan (saludo, agradecimiento, meta-conversación, despedida, follow-up resoluble con el historial provisto) frente a las que recuperan (cualquier pregunta técnica/factual sobre FastAPI), incluye el historial como contexto, delimita el input del usuario como dato y exige salida JSON `{"needs_retrieval": bool, "reason": str}`. Regla explícita: ante duda, `true`.
- [ ] **Config** (`backend/app/config.py`): `intent_gating_enabled: bool = True`, `intent_timeout_s: float = 10.0` (≥10s mínimo de la API, igual que guardrail/rewrite).
- [ ] **Dependencia** `get_intent_gate(settings)` en `router.py`: construye `GeminiChatAdapter` Flash (sin `max_retries`, por el mismo motivo que `get_guardrail`: evitar cliente eager que convierta un 401 en 500) y lo envuelve en `IntentGate`.
- [ ] **Cableado concurrente** en `chat_endpoint` (`router.py`): el gate de intención necesita el historial, así que se carga **antes** (read-only, sin crear sesión: `load_history(body.session_id)` si hay `session_id`, lista vacía si es sesión nueva). Después se lanzan guardrail e intent **en paralelo** con `asyncio.gather` (cada uno en su `asyncio.to_thread`), de modo que la latencia de entrada sea `max(guardrail, intent)`. Toggles independientes: si uno está deshabilitado no se añade a la tupla del `gather`. La creación de sesión (`get_or_create_session`) se mantiene **después** del bloqueo por guardrail, para no crear sesiones vacías por inputs hostiles (comportamiento actual preservado).
- [ ] **Salto de retrieval:** si `not verdict.needs_retrieval` → no se llama a `retrieve`; `candidates=[]`, `citations=[]`; se construye el prompt por el camino sin contexto. Atributos en el span `chat_turn`: `retrieval_skipped=True`, `intent_reason`, e `intent_failed_open` si aplica. Si `needs_retrieval` → pipeline actual intacto.
- [ ] **Camino de prompt sin contexto** (`build_prompt_no_context(query, history)` en `chat/prompts.py`): reutiliza el **mismo** `system.md` v1.3 (preserva las reglas de capa 3) y solo cambia el turno humano: en vez del bloque `<context>`, una instrucción de responder de forma conversacional y breve, basándose en el historial si lo hay, sin inventar documentación. No se toca `system.md`.

## Acceptance criteria

- Saludo ("hola", "gracias") en turno nuevo → `retrieval_skipped=True`, respuesta directa, `citations=[]`, sin llamadas a rewriter/reranker/embeddings/búsqueda.
- Pregunta técnica ("¿cómo defino un query parameter opcional?") → `needs_retrieval=True`, pipeline completo con citas (comportamiento actual).
- Meta-pregunta ("¿qué te he preguntado antes?") con historial → salta retrieval y responde desde el historial.
- Fallo del gate (timeout/parseo) → `failed_open=True` y **recupera** (no salta).
- Latencia de entrada ≈ `max(guardrail, intent)`: verificable en los spans (guardrail e intent solapados en el tiempo, no en serie).
- **Eval gate (`/eval`) sin regresión** antes de cerrar: las preguntas del dataset gold son técnicas → todas deben seguir recuperando; recall@5/MRR y métricas RAGAS dentro de floors.
- Verificación en vivo con curl (saludo salta / técnica recupera / follow-up) antes de cerrar.

## Tests

- `backend/tests/chat/test_intent.py`: parser (JSON con fences, prosa alrededor, verdict desconocido), `needs_retrieval` true/false, **fail-open** ante excepción del LLM (Gemini mockeado). Historial vacío y con turnos.
- `test_router.py` / generación: turno saltado no invoca el orquestador de retrieval (mock de `retrieve` no llamado) y emite citas vacías; turno técnico sí lo invoca.
- `chat/test_prompts.py`: `build_prompt_no_context` incluye el `system.md` (capa 3 intacta) y **no** incluye el bloque `<context>`.

## Risks

- **Falso salto (el caro):** saltar cuando hacía falta retrieval → respuesta sin fundamento. Mitigación: prompt sesgado a `true`, fail-open a retrieve, eval gate como red de seguridad. Decisión registrada en ADR-013.
- **Varianza del free-tier:** respuestas vacías/erróneas del Flash → fail-open cubre el caso (recupera).
- **Follow-up técnico encubierto:** "¿y para el tipo?" tras una pregunta técnica parece trivial pero necesita corpus. El prompt trata como "resoluble con historial" solo lo que el historial ya contesta; ante duda, recupera.
- **Guardrail deshabilitado:** el intent gate corre solo (sin con quién paralelizar); sigue siendo una única llamada Flash en la entrada, aceptable.
