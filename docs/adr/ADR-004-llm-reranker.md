# ADR-004: LLM-as-reranker (RankGPT) vs cross-encoder dedicado

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** retrieval, models

## Contexto

Tras la búsqueda híbrida, necesitamos reordenar los top-K candidatos antes de pasarlos al generador. El patrón estándar es un cross-encoder dedicado (Cohere Rerank, Voyage, BGE). Bajo restricción de cero tarjeta, evaluamos alternativas.

## Drivers

- Cero tarjeta (Cohere/Voyage requieren cuenta de pago).
- Mantener una sola API key.
- Calidad de reranking aceptable (no necesariamente la mejor).
- Latencia tolerable.

## Opciones

- A. Cohere Rerank 3.5 (managed, de pago).
- B. BGE-Reranker-v2-m3 local (cross-encoder open).
- C. LLM-as-reranker (RankGPT) con Gemini Flash.

## Decisión

Opción C. LLM-as-reranker con Gemini Flash siguiendo el patrón RankGPT. Prompt listwise que recibe la query + 20 candidatos y devuelve los IDs reordenados en JSON.

## Consecuencias

### Positivas

- Cero coste con free tier.
- Una sola API key.
- Multilingüe sin ajuste extra.
- Cero infra adicional (cross-encoder requeriría modelo en disco + recursos del alumno).

### Negativas

- Latencia ~800ms-2s vs 100-300ms de cross-encoder.
- Coste por query mayor (consume tokens).
- Dependencia de que el LLM devuelva JSON parseable: requiere parser robusto con fallback.

## Alternativas descartadas

- Cohere/Voyage: rompen cero tarjeta.
- BGE local: requiere ~600MB en disco y recursos de CPU. Lo dejamos como upgrade documentado.
