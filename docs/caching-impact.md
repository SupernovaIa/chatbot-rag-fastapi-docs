# Informe de impacto del caching implícito — Gemini

> Generado: 2026-05-24T16:38:45.253020
> Modelo: `gemini-3.5-flash`
> Endpoint: `http://localhost:8000`
> Session ID: `cbd48365-c266-4c56-9195-934405de3c7b`

## Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Turnos enviados | 5 |
| Turnos completados | 5 |
| Turnos con caching activo | 0 |
| Cache hit rate | 0.0 % |
| Tokens prompt (media) | 0 |
| Tokens cacheados (media, cuando aplica) | 0 |
| Tokens output (media) | 0 |
| TTFT p50 (media) | 9341 ms |
| Duración total (media) | 37129 ms |
| Coste real estimado | $0.000000 |
| Coste hipotético (sin caché) | $0.000000 |
| Ahorro estimado | $0.000000 (0.0 %) |

## Detalle por turno

| Turno | Prompt tokens | Cached tokens | Output tokens | TTFT (ms) | Coste USD | Caché |
|-------|--------------|---------------|---------------|-----------|-----------|-------|
| 1 | 0 | 0 | 0 | 19043 | $0.000000 | ⬜ |
| 2 | 0 | 0 | 0 | 4972 | $0.000000 | ⬜ |
| 3 | 0 | 0 | 0 | 5477 | $0.000000 | ⬜ |
| 4 | 0 | 0 | 0 | 7005 | $0.000000 | ⬜ |
| 5 | 0 | 0 | 0 | 10210 | $0.000000 | ⬜ |

## Interpretación

### Caching implícito de Gemini

El caching implícito de Gemini Flash aplica cuando el prefijo del prompt supera
los **1 024 tokens**. El system prompt de este proyecto mide ~1200 tokens,
por lo que debería ser elegible.

Sin embargo, LangChain en modo streaming no expone `usage_metadata` en los chunks
(Issue #12, bloque CH). Si `cached_tokens = 0` en todos los turnos, el campo
no está disponible en el tier/modelo actual, no que el caching no esté activo.

### Separación de fases

- **Rewriter y reranker**: el prefijo varía por turno (incluye candidatos/historial).
  El caching implícito es esporádico para estas fases.
- **Generador**: el system prompt (~1 200 tokens) es el prefijo estable. Aquí
  el caching tiene más impacto.

### Precios usados

- Input: $0.3/M tokens
- Input cacheado: $0.075/M tokens
- Output: $1.25/M tokens

Ver `docs/cost-model.md` para el modelo completo.