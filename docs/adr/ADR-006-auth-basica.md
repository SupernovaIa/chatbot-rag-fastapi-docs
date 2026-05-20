# ADR-006: Autenticación con FastAPI Users (email + password + JWT)

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** auth, security

## Contexto

Un chatbot en producción siempre lleva auth. Para v1.0.0 queremos auth básica que funcione sin proveedor externo, encaje en el patrón "cero tarjeta" y permita demostrar filtros de permisos, observabilidad por usuario y rate limiting por usuario.

## Drivers

- Sin proveedor externo (cero tarjeta).
- Implementación rápida.
- Desbloquea features pedagógicas: filtros por user_id en retrieval, métricas por user_id en Phoenix, rate limiting por user_id en seguridad.

## Opciones

- A. FastAPI Users con email + password local + JWT httpOnly cookie.
- B. Supabase Auth (free tier sin tarjeta).
- C. Auth0 / Clerk free tier.
- D. Sin auth: chat anónimo con session_id por cookie.

## Decisión

Opción A. FastAPI Users con bcrypt para hash, JWT en cookie httpOnly, tabla `users` en Postgres del proyecto.

## Consecuencias

### Positivas

- Sin proveedor externo: cero tarjeta intacto.
- Postgres existente reutilizado.
- Patrón estándar en backends Python.

### Negativas

- No soporta SSO/OAuth out of the box (extensible si se quiere).
- Reset de password requiere infraestructura email (fuera del scope v1.0).

## Alternativas descartadas

- Supabase Auth: añade dependencia externa, complica el setup local.
- Auth0/Clerk: requieren registro de cuenta y configuración OAuth.
- Sin auth: pierde features pedagógicas clave (filtros, observabilidad por user, rate limiting).

## Notas de implementación

- Cookie httpOnly y SameSite=Lax para evitar XSS y CSRF básico.
- JWT con TTL corto (1h) + refresh token con TTL más largo (7d) en otra cookie httpOnly.
- Sin "remember me" en v1.0 para simplificar.
