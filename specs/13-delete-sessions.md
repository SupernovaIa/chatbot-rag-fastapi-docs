# Spec 13 · Borrado de conversaciones

**Estado:** aceptada
**Bloque:** EV1 (Evolutivo post-1.0)
**Dependencias:** Spec 06 (gestión de historial), Spec 11 (frontend chat), ADR-011 (arquitectura de código). Sin ADR propio: no hay decisión arquitectónica que tomar, el cambio es simétrico al `GET` existente.

## Goal

Permitir que un usuario autenticado borre una de sus conversaciones. Hoy solo existen `POST /chat`, `GET /chat/sessions` y `GET /chat/sessions/{id}`; no hay forma de eliminar.

## User story

> Como usuario autenticado, quiero borrar una conversación de mi lista para retirar las que ya no me interesan, sin poder tocar las de otros usuarios.

## Approach

- [ ] **Backend — store:** método `delete_session(session_id)` en `ChatHistoryStore` (`backend/app/chat/store.py`): `DELETE FROM chat_sessions WHERE id = :id`. Los mensajes caen por `ON DELETE CASCADE` ya definido en la migración `0002` sobre `chat_messages.session_id` → no hay borrado manual de mensajes ni migración nueva.
- [ ] **Backend — endpoint:** `DELETE /chat/sessions/{session_id}` en `router.py`, simétrico al `GET /chat/sessions/{id}`:
  - `store.get_session(id)` → `404 Session not found` si es `None`.
  - `session.user_id != current_user.id` → `403 Forbidden` (no se filtra existencia: mismo orden de checks que el GET).
  - Si OK: `delete_session(id)` y respuesta `204 No Content`.
- [ ] **Frontend — api:** `deleteSession(sessionId)` en `frontend/src/api/chat.ts`, mismo patrón `fetch` + `credentials: "include"`, lanza si `!res.ok`.
- [ ] **Frontend — UI:** botón de borrado por ítem en `SessionSelector.tsx`. `onClick` con `stopPropagation` (no debe disparar `onSelectSession`), `window.confirm` antes de borrar, y al confirmar llama a `deleteSession` y refresca la lista (`fetchSessions`). Si la sesión borrada es la activa, se resetea a `null`.

## Acceptance criteria

- `DELETE` de una sesión propia → `204`; la sesión y sus mensajes desaparecen (cascade verificado).
- `DELETE` de una sesión de otro usuario → `403`, sin borrar nada.
- `DELETE` de un `id` inexistente → `404`.
- Verificación en vivo con curl y dos usuarios distintos antes de tocar el frontend (propia / 403 / 404).
- Botón en `SessionSelector` con confirmación; tras borrar, la lista se refresca y no queda seleccionada una sesión inexistente.

## Tests

- `test_router.py`: borrar la propia (`204`), `403` sobre ajena, `404` si no existe.

## Risks

- **Orden de checks:** comprobar existencia antes que propiedad (igual que el GET) evita un 403 sobre algo que no existe; se mantiene consistencia, no se considera fuga de información en este contexto.
- **Idempotencia:** un segundo `DELETE` de la misma sesión devuelve `404` (ya no existe). Aceptable para v1; no se persigue idempotencia estricta.
