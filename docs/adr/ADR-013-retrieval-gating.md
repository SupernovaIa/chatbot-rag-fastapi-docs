# ADR-013: Retrieval gating — clasificador de intención Gemini Flash concurrente con el guardrail

**Estado:** aceptado
**Fecha:** 2026-05-26
**Tags:** retrieval, chat, latency, cost

## Contexto

El pipeline de `/chat` ejecuta siempre `rewrite → retrieve → rerank` antes de generar (`backend/app/chat/router.py`, `backend/app/retrieval/orchestrator.py`). Pero hay turnos que no necesitan tocar el corpus: saludos ("hola"), agradecimientos ("gracias, perfecto"), meta-preguntas sobre la propia conversación ("¿qué te pregunté antes?") y follow-ups que se resuelven con el historial ya cargado. Para esos turnos el retrieval gasta dos llamadas extra a Gemini Flash (rewriter + reranker), embeddings y una búsqueda híbrida, sumando latencia y coste sin aportar contexto útil.

Queremos una capa previa que decida si el turno necesita retrieval y, si no, lo salte y responda directo. La decisión a tomar: **cómo** se clasifica la intención del turno.

## Drivers

- **Bajar latencia y coste por turno en los casos sin retrieval**, que es el objetivo medible del evolutivo.
- **No regresar la calidad de respuesta:** saltar retrieval cuando *sí* hacía falta (responder sin fundamento una pregunta técnica) es el fallo caro. El eval gate es la red de seguridad.
- **No añadir latencia neta en los casos que sí recuperan.** Una llamada LLM extra y secuencial penalizaría todos los turnos, incluidos los mayoritarios que sí necesitan corpus.
- **Mantenibilidad y consistencia** con el patrón ya presente (capa 2 guardrail): puerto fino, prompt versionado, fail-open, settings con toggle.

## Opciones consideradas

- **A. Clasificador Gemini Flash de intención, concurrente con el guardrail de capa 2.**
- **B. Heurístico determinista** (reglas: regex/listas de saludos-agradecimientos-meta, longitud, ausencia de términos técnicos, señal de follow-up por historial).
- **C. Clasificador Gemini Flash secuencial** (segunda llamada Flash después del guardrail).

## Decisión

Opción A.

Un clasificador de intención sobre Gemini Flash (`IntentGate`, puerto fino propio) decide `needs_retrieval` sí/no. La clave que hace viable un LLM aquí es la **concurrencia**: la ruta de entrada de `/chat` ya hace una llamada Flash por turno (el guardrail de capa 2, `guardrail.classify`). El gate de intención se lanza **a la vez** que el guardrail con `asyncio.gather`, de modo que la latencia de la fase de entrada es `max(guardrail, intent)` ≈ un round-trip, no la suma `guardrail + intent`. Sin esta concurrencia el LLM no sería defendible (doblaría la latencia de entrada de cada turno).

Restricciones de diseño:

- **Puerto fino propio (`IntentGate`)**, separado del guardrail de seguridad, con su prompt versionado en `prompts/intent_gate.md`, inyectado con `Depends` y mockeable en tests (ADR-011). **No** se funde el prompt de intención con el de seguridad: son dos responsabilidades distintas (clasificar intención vs detectar ataque) y mezclarlas degrada ambos.
- **Fail-open hacia retrieve:** si el gate falla (timeout, error de parseo, API caída) o duda, se recupera. El prompt se sesga explícitamente a `needs_retrieval=true` ante cualquier ambigüedad, porque el falso salto es el fallo caro.
- **Camino de prompt sin contexto** para los turnos saltados que **no** toca las reglas de la capa 3 del `system.md` v1.3: se reutiliza el mismo system prompt (preservando las reglas de seguridad) y solo cambia el turno humano, que en vez del bloque `<context>` lleva una instrucción de responder de forma conversacional sin documentación.

## Consecuencias

### Positivas

- Latencia y coste menores en los turnos sin retrieval (se eliminan rewriter + reranker + embeddings + búsqueda).
- Coste de la decisión ≈ 0 en latencia gracias a la concurrencia con el guardrail; el gate "se esconde" detrás de una llamada Flash que ya existía.
- Generaliza ante lenguaje natural real (paráfrasis, idiomas mezclados, formas no previstas) mejor que un set de reglas.
- Consistente con el patrón del guardrail (puerto, prompt versionado, fail-open, toggle), fácil de mantener.

### Negativas

- Depende de una llamada LLM con varianza del free-tier; mitigado con fail-open hacia retrieve y un toggle de configuración (`intent_gating_enabled`).
- El camino de prompt sin contexto es un segundo modo de generación que hay que mantener y cubrir con tests.
- Si el guardrail está deshabilitado, el gate corre solo (sin nadie con quien paralelizar): sigue siendo una única llamada Flash en la ruta de entrada, aceptable.

## Alternativas descartadas

- **B. Heurístico determinista:** frágil ante lenguaje natural real — paráfrasis de saludos, agradecimientos en otros idiomas, follow-ups redactados de mil formas. Mantener y ampliar reglas para cubrir la cola larga es trabajo continuo y la tasa de falso salto sería difícil de acotar. Descartado por cobertura.
- **C. Flash secuencial:** misma capacidad de clasificación que A pero **dobla la latencia de la ruta de entrada** (guardrail + intent en serie) sin necesidad, cuando ambos pueden correr en paralelo. Descartado por latencia.

## Notas

- El gate corre dentro del span `chat_turn`; la decisión se registra como atributos (`retrieval_skipped`, `intent_reason`, `intent_failed_open`) para observabilidad en Phoenix.
- El gate **necesita el historial** ya cargado para clasificar follow-ups, así que se ubica después de cargar la sesión/historial pero antes del retrieval. El guardrail no lo necesita; por eso el `gather` agrupa la clasificación de intención con el guardrail manteniendo el orden lógico del pipeline (ver spec 14 para el detalle del cableado).
