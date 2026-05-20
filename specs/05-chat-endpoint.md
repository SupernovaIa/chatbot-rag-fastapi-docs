# Spec 05 · Endpoint /chat con streaming SSE

**Estado:** aceptada
**Bloque:** CH (Backend de chat)
**Dependencias:** Spec 02, 03, 04, 06, 07

## Goal

Endpoint POST `/chat` que recibe una query y `session_id`, orquesta el pipeline RAG completo (rewrite → retrieve → rerank → generate) y devuelve la respuesta en streaming SSE con citas.

## User story

> Como cliente del backend, llamo POST `/chat` con la query y el session_id, y recibo tokens en streaming a medida que el modelo genera, terminando con las citas estructuradas como evento final.

## Approach

- [ ] Ruta protegida por JWT (cookie httpOnly).
- [ ] Validación de entrada con Pydantic: `query: str`, `session_id: UUID` (opcional, se crea si no viene).
- [ ] Pipeline: cargar últimos N turnos → rewriter → retrieve híbrido → rerank → construir prompt con system + history + context + query → llamada streaming a Gemini.
- [ ] Cada token se emite como SSE event `data: {"type": "token", "content": "..."}`.
- [ ] Al final del stream, evento `data: {"type": "citations", "items": [...]}`.
- [ ] Persistencia: el turno completo (query, respuesta, citas) se guarda en `chat_messages` al cerrar el stream.

## Acceptance criteria

- `curl -N -H "Cookie: jwt=..." -d '{"query": "..."}' http://localhost:8000/chat` devuelve stream.
- Test de integración: stream completo termina con evento `citations`.
- Test: sin auth, responde 401.
- Latencia TTFT (Time To First Token) < 3s p95.
- Trazas Phoenix muestran fases completas con latencias.

## Riesgos

- Cliente desconecta a mitad del stream → debe cancelar la generación del LLM para no gastar tokens.
- Errores parciales en el stream (p. ej. retrieval falla) → emitir evento `error` y cerrar limpio.

## Preguntas abiertas

- ¿SSE puro o WebSocket? Default SSE por simplicidad.
- ¿Generamos `session_id` server-side o lo manda el cliente? Default server-side si no viene.
