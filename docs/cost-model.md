# Modelo de coste — Gemini API

> **Nota sobre el free tier**: este proyecto corre en el free tier de Google AI Studio (sin tarjeta). Los valores económicos que aparecen en los spans de Phoenix son **informativos**: muestran el coste equivalente si se migrase a un tier de pago, y sirven como métrica para comparar optimizaciones (caching, longitud de prompts, número de candidatos del reranker).

## Tabla de precios

Anclado: **2026-05-20**
Fuente: [Google AI Studio Pricing](https://ai.google.dev/pricing)

| Modelo | Rol en el proyecto | Input ($/M tokens) | Input cacheado ($/M) | Output ($/M tokens) |
|--------|-------------------|--------------------|-----------------------|---------------------|
| `gemini-3.5-flash` | Generación, reranker, rewriter | $0.30 | $0.075 | $1.25 |
| `gemini-3-pro-preview` | Juez de evals (RAGAS) | $1.25 | $0.3125 | $5.00 |

> El caching implícito de Gemini aplica un **descuento del 75 %** sobre el precio de input cuando el prefijo del prompt se sirve desde caché. Para que el caching implícito sea elegible, el prefijo debe superar los **1 024 tokens** (mínimo documentado para Gemini Flash). El system prompt de este proyecto mide entre 1 107 y 1 302 tokens (medido con el SDK directo).

## Desglose por turno de chat

Para un turno típico (query en español, historial N=0, top-5 rerank, respuesta ~250 tokens):

| Fase | Input tokens | Cached tokens | Output tokens | Coste estimado |
|------|-------------|---------------|---------------|----------------|
| Rewriter (Flash) | ~300 | 0 | ~50 | $0.000107 |
| Reranker (Flash) | ~2 000 | 0 | ~80 | $0.000700 |
| Generador (Flash) | ~2 500 | ~1 200 (system prompt) | ~250 | $0.000704 |
| **Total** | **~4 800** | **~1 200** | **~380** | **$0.001511** |

> Nota: el rewriter y el reranker no reutilizan el mismo prefijo que el generador (prompts distintos), por lo que **el caching implícito solo aplica de forma consistente al generador**. En el reranker el prefijo varía por turno (incluye los candidatos), así que el caching es esporádico.

## Impacto del caching implícito

Si el caching implícito está activo para el generador (~1 200 tokens del system prompt):
- **Sin caching:** 2 500 tokens × $0.30/M = $0.000750
- **Con caching (1 200 tokens a $0.075/M + 1 300 tokens a $0.30/M):** $0.000090 + $0.000390 = $0.000480
- **Ahorro por turno:** $0.000270 (36 % de la generación)

Ver `docs/caching-impact.md` para la medición empírica con el stack real.

## Cómo se adjunta al span de Phoenix

El módulo `backend/app/observability/cost.py` expone `compute_cost(usage, model) → QueryCost`. El router de chat lo llama al final del stream y adjunta los valores al span `generate`:

```
generate.cost_usd          # coste total del turno
generate.input_usd         # coste input no cacheado
generate.cached_usd        # coste input cacheado
generate.output_usd        # coste output
generate.cache_hit_rate    # fracción de input tokens desde caché
generate.savings_usd       # ahorro vs. todo a precio de input
```

Y al span `chat_turn`:
```
chat_turn.total_cost_usd   # suma de generador + reranker + rewriter
```

## Actualización de precios

Para actualizar la tabla, editar `_PRICING` en `backend/app/observability/cost.py` y esta tabla. Convención de commits: `chore(cost): update Gemini pricing YYYY-MM-DD`.

## Proyección mensual (escenario de estudio)

| Volumen | Turnos/día | Turnos/mes | Coste/mes (estimado) |
|---------|-----------|------------|---------------------|
| Uso ligero | 20 | 600 | $0.91 |
| Uso moderado | 100 | 3 000 | $4.53 |
| Demo pública | 500 | 15 000 | $22.65 |

> Proyección con caching activo y mix típico de queries. Sin caching el coste se incrementa ~15 %.
