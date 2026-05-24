# Impacto del caching implícito de Gemini — Medición

> Este fichero documenta la metodología de medición y los números obtenidos con el stack real.
> Para ejecutar la medición: `python scripts/measure_caching_impact.py`
> Para actualizar este fichero con datos reales: `python scripts/measure_caching_impact.py --output docs/caching-impact.md`

## Contexto

Gemini Flash aplica **caching implícito** cuando el prefijo del prompt supera los 1 024 tokens. Para el chatbot RAG, el prefijo estable es el **system prompt** (`prompts/system.md`), cuyo tamaño medido es de ~1 107–1 302 tokens (según el historial y el bloque de contexto del primer mensaje).

El campo `cached_content_token_count` de la API de Gemini indica cuántos tokens de input se sirvieron desde caché. Un valor > 0 confirma que el caching implícito está activo para ese turno.

## Limitación conocida: streaming y LangChain (Issue #12)

LangChain `ChatGoogleGenerativeAI` en modo `astream()` no expone `usage_metadata` en los chunks intermedios del stream. El SDK solo reporta usage en la respuesta completa (no-streaming). Por este motivo:

- En modo streaming, `cached_content_token_count` puede aparecer como `None` o `0` aunque el caching esté activo.
- El script `measure_caching_impact.py` intenta recuperar los valores desde los spans de Phoenix (que sí capturan el `response_metadata` del último chunk), pero si el campo sigue siendo 0, se trata como "caching no disponible" en este tier/modelo.

## Metodología de medición

```
python scripts/measure_caching_impact.py \
    --turns 10 \
    --base-url http://localhost:8000 \
    --email <email> \
    --password <password>
```

El script:
1. Autentica y crea una sesión de chat nueva.
2. Envía N turnos con queries variadas del corpus de FastAPI.
3. Para cada turno, recupera los atributos `prompt_tokens`, `cached_tokens`, `output_tokens` desde el span `generate` en Phoenix.
4. Calcula la cache hit rate, el ahorro estimado y la TTFT media.

## Resultados

> **Estado: pendiente de medición con stack real.**
>
> Ejecutar `python scripts/measure_caching_impact.py` con el stack levantado y la `GOOGLE_API_KEY` configurada para obtener los números reales. Los valores de abajo son estimaciones basadas en el diseño del sistema.

### Estimación teórica (5 turnos, sistema en frío)

| Métrica | Valor estimado |
|---------|---------------|
| Turnos enviados | 5 |
| Cache hit rate | 0 % (turno 1 fría) → potencialmente 40–80 % (turno 2+) |
| Tokens prompt (media) | ~2 500 |
| Tokens cacheados (media) | ~1 200 (system prompt, si caching activo) |
| Tokens output (media) | ~250 |
| TTFT p50 | ~2 000 ms |
| Coste real (5 turnos, con caché) | ~$0.007 |
| Coste hipotético (sin caché) | ~$0.009 |
| Ahorro estimado | ~$0.002 (22 %) |

### Condiciones que activan el caching

1. **System prompt > 1 024 tokens**: ✅ (~1 200 tokens medidos en bloque CH).
2. **Prefix estable entre turnos**: ✅ El `SystemMessage` siempre es el mismo contenido del fichero `prompts/system.md`.
3. **Model ID elegible**: ⚠️ El caching implícito está documentado para modelos `gemini-*-flash`. Con `gemini-3.5-flash` (ID anclado 2026-05-20), debería estar disponible.
4. **Tier**: ⚠️ El free tier puede no reportar `cached_content_token_count` incluso cuando el caching esté activo (no cobra el cache hit, por lo que no lo reporta). Esto es coherente con la observación de Issue #12.

## Interpretación por fase

| Fase | Prefijo estable | Caching esperado |
|------|----------------|-----------------|
| Rewriter | Prompt de rewrite (varía por historial) | Bajo |
| Reranker | Prompt de rerank + candidatos (varía) | Muy bajo |
| **Generador** | **System prompt (~1 200 tokens)** | **Alto** |

El caching implícito es más valioso en el generador, que es también la llamada de mayor coste (más tokens de input y output).

## Instrucciones para actualizar

Cuando tengas el stack levantado con la API key real:

```bash
# Instalar httpx si no está disponible fuera del contenedor
pip install httpx

# Medir y actualizar este fichero
python scripts/measure_caching_impact.py \
    --turns 10 \
    --email tu@email.com \
    --password tu_password \
    --output docs/caching-impact.md
```

Los números reales reemplazarán la sección "Estimación teórica" de este fichero.

## Referencias

- Issue #12: [LangChain streaming no expone usage_metadata]
- ADR-008: Observabilidad Phoenix self-host
- `docs/cost-model.md`: modelo de precios Gemini
- `backend/app/observability/cost.py`: calculadora de coste
- `backend/app/chat/router.py`: captura de `cached_content_token_count` en el span `generate`
