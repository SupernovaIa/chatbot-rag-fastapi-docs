# Spec 07 · Gemini context caching (implícito)

**Estado:** aceptada
**Bloque:** CH (Backend de chat)
**Dependencias:** Spec 05 (chat endpoint)

## Goal

Reducir coste y latencia reutilizando la parte estable del prompt (system prompt + instrucciones de formato + ejemplos de citas) mediante el caching implícito de Gemini, que aplica un descuento sobre los tokens repetidos sin gestionar un cache explícito.

## Contexto técnico

Gemini ofrece dos modos de caching:

- **Implícito:** activado por defecto en Gemini 2.5 y posteriores. Mínimo ~1.024 tokens (Flash) / ~2.048 (Pro) en el prefijo común. 90% de descuento sobre los tokens cacheados. No requiere crear ni gestionar un `cache_id`.
- **Explícito (`CachedContent`):** da control y descuento garantizado, pero exige un mínimo de **32.768 tokens** de contenido cacheado. El system prompt de este proyecto no se acerca a ese umbral, así que el caching explícito **no aplica**.

Decisión: apoyarse en el caching implícito. La optimización es estructural, no de gestión de cache.

## User story

> Como sistema, quiero que la parte estable del prompt (system + formato + ejemplos) sea idéntica y vaya al principio en cada query, para que Gemini reutilice esos tokens con el descuento de caching implícito.

## Approach

- [ ] Estructurar el prompt con prefijo estable primero: `system prompt` + instrucciones de formato + ejemplos de citas. Después, el contenido dinámico: contexto recuperado + historial + query.
- [ ] El prefijo estable debe superar el mínimo (~1.024 tokens) para que el caching implícito se active. Si no llega, documentarlo: a esta escala el ahorro es marginal.
- [ ] No crear `CachedContent` ni gestionar `cache_id`/TTL: el caching implícito es automático.
- [ ] Versionado del prompt como artefacto (`prompts/system.md`): un cambio del prefijo rompe la reutilización hasta que se estabiliza de nuevo. Documentar el hash del prompt en la traza.

## Acceptance criteria

- El prompt se construye con el prefijo estable al principio, idéntico entre queries.
- Tracing de Phoenix muestra `cached_token_count` y `prompt_token_count` por query; a partir del segundo turno con prefijo estable, `cached_token_count` > 0.
- Métrica medible en Bloque F: reducción de tokens facturados con caching implícito (si el prefijo supera el mínimo).
- Test: dos queries consecutivas con el mismo prefijo reportan tokens cacheados en la metadata de uso.

## Riesgos

- Si el prefijo estable no supera ~1.024 tokens, el caching implícito no se activa y el ahorro es nulo. Verificar el tamaño real del prompt y documentarlo.
- El caching implícito no garantiza el hit (best-effort). La métrica del Bloque F se mide, no se asume.

## Preguntas abiertas

- ¿Engordar el prefijo con ejemplos para superar el mínimo y forzar caching? Solo si el ejemplo aporta calidad; no inflar artificialmente.
- ¿Cachear contexto recuperado? No: cambia por query, es contenido dinámico.
