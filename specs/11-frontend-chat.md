# Spec 11 · Frontend de chat

**Estado:** aceptada
**Bloque:** D (Frontend chat completo)
**Dependencias:** Spec 05 (endpoint `/chat` SSE), ADR-006 (auth en cookie), ADR-009 (frontend separado), `docs/design-system.md`

## Goal

Interfaz web de chat sobre el endpoint `/chat` SSE: conversación en streaming token a token, citas clicables que abren el chunk fuente, sesiones persistentes y multi-turno, sobre el scaffold de auth del Bloque AU (login/register/routing protegido). Estilo según `docs/design-system.md`, UI minimal.

## User story

> Como usuario autenticado, quiero escribir preguntas y ver la respuesta aparecer en streaming con sus citas, poder abrir el fragmento citado, y retomar conversaciones anteriores, todo desde una UI sencilla.

## Approach

- [ ] Hook `useChatStream`: consume el SSE de `/chat`, maneja los eventos `token`, `citations` y `error`, expone el estado de streaming, y cancela la conexión al desmontar o al cambiar de sesión.
- [ ] `ChatInput`: campo de entrada con envío, deshabilitado durante el streaming.
- [ ] `MessageList` + `Message`: render de la conversación; `Message` renderiza markdown y resuelve las citas `[1]`, `[2]` a chips clicables.
- [ ] `CitationsPanel`: muestra el chunk fuente al hacer clic en una cita.
- [ ] `SessionSelector`: lista las sesiones del usuario y permite retomarlas; las sesiones persisten tras refresh.
- [ ] Integración en la página de chat sobre el routing protegido existente.
- [ ] Build de producción: `Dockerfile.prod` con nginx, proxy `/api/*` al backend, perfil `prod` en `docker-compose.yml`.
- [ ] **Sanitización del HTML** que renderiza react-markdown: el contenido de los chunks es input no confiable (corpus), no debe ejecutar HTML/script.

## Acceptance criteria

- Flujo completo register → login → chat → multi-turno → logout funciona en dev (`:5173`) y en prod local (`:80`).
- El stream se ve token a token; al cerrar llega el evento `citations`.
- Las citas `[1]`/`[2]` son chips clicables que abren el chunk correspondiente en `CitationsPanel`.
- Un 2º turno con la misma sesión mantiene el contexto; las sesiones persisten tras refresh (`SessionSelector` las carga).
- El proxy `/api/*` resuelve al backend en el build de prod local.
- Un chunk con HTML/script incrustado se renderiza como texto, no se ejecuta (XSS).

## Verificación

Parte la puede comprobar el agente (build dev y prod, SSE por `curl -N` con cookie, sanitización con input controlado, `tsc`/lint). La parte visual (streaming en pantalla, citas clicables, persistencia, flujo en navegador) la verifica Javi con una checklist corta que el agente deja preparada.

## Riesgos

- XSS desde el contenido de los chunks vía react-markdown. Mitigar con sanitización explícita.
- Sin tests automáticos de frontend en v1.0 (decisión de alcance): la verificación es el flujo en vivo. Deuda documentada en issue de follow-up.
- Reconexión/cancelación del SSE mal manejada deja conexiones colgadas y gasta free tier. El hook cancela al desmontar/cambiar de sesión.

## Preguntas abiertas

- ¿Reintento automático del SSE si la conexión cae a mitad de stream? Default v1.0: no, el usuario reenvía.
