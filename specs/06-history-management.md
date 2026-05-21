# Spec 06 · Gestión de historial multi-turn

**Estado:** aceptada
**Bloque:** CH (Backend de chat)
**Dependencias:** ADR-005 (sliding window N=5)

## Goal

Persistir el historial conversacional server-side por sesión y exponerlo al pipeline RAG mediante una ventana deslizante de los últimos N=5 turnos.

## User story

> Como sistema, quiero que el agente recuerde los últimos 5 turnos de cada conversación, sin acumular contexto indefinidamente.

## Approach

- [ ] Tabla `chat_sessions`: `id UUID, user_id, created_at, updated_at`.
- [ ] Tabla `chat_messages`: `id, session_id, turn_idx, role (user|assistant), content, citations jsonb, created_at`.
  - Constraint UNIQUE `(session_id, turn_idx, role)` — no `(session_id, turn_idx)`: cada turno genera **dos** filas (una con `role='user'` y otra con `role='assistant'`), ambas con el mismo `turn_idx`. Una constraint sobre solo `(session_id, turn_idx)` rechazaría la segunda inserción.
- [ ] Al recibir un turno: cargar últimos 5 pares (user + assistant) de la sesión, pasar al pipeline.
- [ ] Al final del turno: insertar mensaje user y mensaje assistant con sus citas.
- [ ] No se borran mensajes antiguos: la ventana es solo de lectura para el prompt.
- [ ] Endpoint `GET /chat/sessions` para listar sesiones del usuario.
- [ ] Endpoint `GET /chat/sessions/{id}` para histórico completo de una sesión.

## Acceptance criteria

- Crear sesión y mantener 7 turnos → al octavo turno, el rewriter recibe solo los últimos 5.
- Reload de la página → el usuario ve su histórico completo desde la BBDD.
- Test: insertar mensaje no rompe IDs/turn_idx consistentes.
- Trazas: cada turno emite span con `session_id`, `turn_idx`, `history_turns_loaded`.

## Riesgos

- Concurrencia: dos turnos simultáneos en la misma sesión podrían colisionar en turn_idx. Mitigar con `SERIALIZABLE` o índice único.
- Sesiones huérfanas si el usuario cierra el navegador a medio turno. Acepable; turn_idx no avanza.

## Preguntas abiertas

- ¿Resumen del historial cuando supera N=5 (futuro)? Anotar como evolución, no implementar.
- ¿Soft delete vs hard delete de sesiones? Default: hard delete con confirmación.
