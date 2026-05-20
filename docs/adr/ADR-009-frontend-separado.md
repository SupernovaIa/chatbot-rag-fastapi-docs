# ADR-009: Frontend React + Vite en contenedor separado del backend

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** frontend, architecture

## Contexto

Decidir cómo se sirve el frontend de chat: como aplicación independiente o servido por el backend.

## Drivers

- Mirror de la arquitectura de producción (frontend en CDN/Static Web Apps, backend como API).
- Independencia de despliegue.
- Coherencia con C4 Level 2 del proyecto.

## Opciones

- A. Frontend en contenedor propio (Vite dev / nginx prod local), backend separado.
- B. Frontend servido por FastAPI desde `/static`.
- C. Frontend en Vercel/Netlify y backend separado.

## Decisión

Opción A. Frontend en su contenedor: Vite dev server con hot reload en dev, nginx sirviendo el build estático en prod local. Comunicación con el backend vía HTTP en local (localhost) y HTTPS en producción, con CORS configurado y JWT en cookie httpOnly. El flag `Secure` de la cookie solo aplica en producción (HTTPS); en local va sin él.

## Consecuencias

### Positivas

- Mismo modelo mental que producción.
- Hot reload en dev sin reiniciar backend.
- Frontend desplegable a Azure Static Web Apps en el anexo (v1.1) sin cambios.

### Negativas

- Un contenedor más en docker-compose.
- CORS a configurar explícitamente.

## Alternativas descartadas

- Frontend servido por FastAPI: rompe el patrón de producción real, dificulta el camino a SWA en Azure.
- Vercel/Netlify: requieren cuenta, fuera del scope cero tarjeta local.
