# Informe de impacto del caching implícito — Gemini

> Generado: 2026-05-24T18:48:25.345927
> Modelo: `gemini-3.5-flash`
> Endpoint: `http://localhost:8000`
> Session ID: `f2baaac0-6373-42d2-8828-b57bedff15b9`

## Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Turnos enviados | 5 |
| Turnos completados | 5 |
| Turnos con caching activo | 1 |
| Cache hit rate | 20.0 % |
| Tokens prompt (media) | 3198 |
| Tokens cacheados (media, cuando aplica) | 4060 |
| Tokens output (media) | 1678 |
| TTFT p50 (media) | 6286 ms |
| Duración total (media) | 23257 ms |
| Coste real estimado | $0.014373 |
| Coste hipotético (sin caché) | $0.015286 |
| Ahorro estimado | $0.000913 (6.0 %) |

## Detalle por turno

| Turno | Prompt tokens | Cached tokens | Output tokens | TTFT (ms) | Coste USD | Caché |
|-------|--------------|---------------|---------------|-----------|-----------|-------|
| 1 | 2653 | 0 | 1309 | 5130 | $0.002432 | ⬜ |
| 2 | 2508 | 0 | 1505 | 6063 | $0.002634 | ⬜ |
| 3 | 3282 | 0 | 1874 | 6589 | $0.003327 | ⬜ |
| 4 | 3282 | 0 | 1874 | 6589 | $0.003327 | ⬜ |
| 5 | 4266 | 4060 | 1829 | 7060 | $0.002653 | ✅ |

## Interpretación

### Tokens y coste

Los conteos de tokens se leen de `chunk.usage_metadata` (campo directo del
`AIMessageChunk`). LangChain-Google-GenAI usa nombres distintos a los del
proto de Gemini:

| LangChain | Gemini proto | Campo en UsageMeta |
|---|---|---|
| `input_tokens` | `prompt_token_count` | `prompt_token_count` |
| `output_tokens` | `candidates_token_count + thoughts_token_count` | `candidates_token_count` |
| `input_token_details["cache_read"]` | `cached_content_token_count` | `cached_content_token_count` |

Nota: `output_tokens` incluye reasoning tokens internos de modelos con thinking
(p. ej. Gemini Flash). Ambos se facturan al precio de output.

### Caching implícito de Gemini

El caching implícito aplica cuando el prefijo del prompt supera
los **1 024 tokens**. El system prompt de este proyecto mide ~1200 tokens,
por lo que el prefijo es elegible en tamaño.

Si `cached_tokens = 0` en todos los turnos, las causas probables son:

1. **Prefijo inestable**: cada turno incluye chunks de retrieval distintos,
   lo que cambia el prefijo y hace que Gemini no encuentre una entrada cacheada.
2. **Tier gratuito**: el caching implícito puede no estar disponible o garantizado
   en el free tier de Google AI Studio.
3. **TTL no alcanzado**: el caching requiere que el mismo prefijo se repita
   varias veces en una ventana de tiempo.

### Separación de fases

- **Rewriter y reranker**: el prefijo varía por turno (incluye candidatos/historial).
  El caching implícito no aplica aquí.
- **Generador**: el system prompt es el prefijo estable, pero los chunks de
  retrieval varían. El caching aplica solo si el sistema prompt ocupa la mayor
  parte del prefijo y los chunks son secundarios.

### Precios usados

- Input: $0.3/M tokens
- Input cacheado: $0.075/M tokens
- Output: $1.25/M tokens

Ver `docs/cost-model.md` para el modelo completo.