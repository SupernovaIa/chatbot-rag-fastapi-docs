# ADR-007: RAGAS con Gemini Pro como juez de evaluación

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** evals, models

## Contexto

Evaluación automática del pipeline RAG con métricas estándar (faithfulness, answer relevance, context precision/recall) requiere un LLM como juez. Bajo restricción cero tarjeta, evaluamos qué modelo y framework usar.

## Drivers

- Métricas estándar del campo (faithfulness, answer relevancy, context precision/recall, recall@K, MRR).
- Reproducibilidad.
- Integración con Pytest para CI.
- Cero tarjeta.

## Opciones

- A. RAGAS con Gemini Pro como juez.
- B. RAGAS con Gemini Flash como juez.
- C. DeepEval con Gemini Pro.
- D. Implementación custom de métricas.

## Decisión

Opción A. RAGAS con Gemini Pro como juez. Generador del sistema sigue siendo Gemini Flash (modelo distinto para reducir sesgo de auto-aprobación; mismo proveedor, aislamiento parcial).

## Consecuencias

### Positivas

- RAGAS es estándar de facto en el campo, métricas bien definidas.
- Gemini Pro mejor instruction following como juez.
- Integración Pytest nativa.

### Negativas

- Mismo proveedor para generador y juez: sesgo de auto-aprobación parcial. Documentado.
- Free tier de Gemini Pro más limitado que Flash. Evals masivas pueden saturar; mitigar con batching y rate limit.

## Alternativas descartadas

- DeepEval: más amplio, útil cuando se añade tool use; en v1.0 RAGAS basta.
- Custom: reinventa la rueda; los matices de LLM-as-judge ya están resueltos en RAGAS.

## Notas

- Validar el juez con anotación humana en un subset de 5-10 ejemplos antes de confiar en sus números.
- Si en futuro se añade segunda API (p. ej. Anthropic con tarjeta), considerar mover el juez a Claude Sonnet para aislamiento completo.
