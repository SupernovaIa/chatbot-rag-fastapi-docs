# ADR-011: Arquitectura de código — package-by-feature con puertos para dependencias externas

**Estado:** aceptado
**Fecha:** 2026-05-21
**Tags:** architecture, code, foundational

## Contexto

El backend integra varias dependencias externas (Gemini, pgvector, Azurite Blob) y crece por features (indexing, retrieval, chat, auth, evals, security, observability), cada una construida en un bloque distinto. Necesitamos una convención de estructura que dé consistencia entre bloques y permita testear sin llamar a servicios reales, sin la ceremonia de una arquitectura hexagonal completa.

## Drivers

- Consistencia entre bloques: cada sesión construye una feature y todas deben encajar igual.
- Testabilidad: mockear Gemini y la BD en tests unitarios (las specs ya lo asumen).
- Portabilidad: migrar a stack gestionado (Azure) cambiando adaptadores, no lógica.
- Proporcionalidad: el foco de la lección es AI engineering, no capas de arquitectura.

## Opciones consideradas

- A. Package-by-feature + puertos finos para dependencias externas.
- B. Hexagonal / ports & adapters estricto (domain / application / infrastructure).
- C. Sin convención (estructura ad-hoc por bloque).

## Decisión

Opción A.

- **Estructura por feature:** `backend/app/<feature>/` (indexing, retrieval, chat, auth, evals, security, observability). Cada feature agrupa su router, su lógica y sus modelos.
- **Puertos para dependencias externas:** las integraciones con servicios externos (LLM Gemini, vector store pgvector, blob Azurite) se acceden detrás de una interfaz fina (`Protocol` o ABC), con una implementación concreta (adaptador). Permite inyectar un doble en tests y cambiar de proveedor sin tocar la lógica de la feature.
- **Sin capas de dominio formales:** no hay separación domain/application/infrastructure ni DTOs/mappers entre capas. La lógica vive en funciones/servicios de la feature; Pydantic cubre entrada/salida.
- **Inyección de dependencias** vía `Depends` de FastAPI para el wiring; sin contenedor DI pesado.

## Consecuencias

### Positivas

- Estructura predecible y consistente entre bloques.
- Tests unitarios sin red (Gemini/pgvector mockeados en el puerto).
- Migración a Azure = nuevo adaptador, misma lógica.
- Sin ceremonia: el alumno se centra en el pipeline RAG.

### Negativas

- Los puertos añaden algo de indirección frente a llamar al SDK directo.
- No es hexagonal puro: si el proyecto creciera mucho, habría que introducir capas. Documentado como evolución.

## Alternativas descartadas

- Hexagonal estricto: ceremonia desproporcionada para el tamaño; desvía el foco de AI engineering.
- Sin convención: el agente improvisaría una estructura distinta en cada bloque, perdiendo consistencia.

## Notas

- Puertos naturales del proyecto: cliente de embeddings/generación (Gemini), `store` del vector store (pgvector), loader de blobs (Azurite). Mantenerlos finos: una interfaz por necesidad real, sin especular.
