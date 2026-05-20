# Spec 10 · Evaluación + CI con gate del PR

**Estado:** aceptada
**Bloque:** E (Evaluación + CI)
**Dependencias:** Spec 08 (dataset gold), ADR-007 (RAGAS + Gemini Pro juez)

## Goal

Ejecutar el dataset gold contra el pipeline en cada PR, calcular métricas estándar de RAG con RAGAS, y bloquear el merge si caen por debajo del threshold.

## User story

> Como mantenedor, quiero que ningún PR se mergee si baja faithfulness, recall@5 u otra métrica clave. La regresión no debe llegar a main.

## Approach

- [ ] Tests Pytest parametrizados en `backend/tests/evals/test_pipeline.py` que cargan `gold.jsonl` y ejecutan el pipeline.
- [ ] Métricas con RAGAS: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`. Custom: `recall@5`, `MRR`.
- [ ] Juez: Gemini Pro (configurado en RAGAS).
- [ ] Thresholds en `tests/evals/thresholds.yaml`: faithfulness ≥0.75, answer_relevancy ≥0.8, context_precision ≥0.7, context_recall ≥0.8, recall@5 ≥0.85, MRR ≥0.6.
- [ ] El runner registra cada ejecución de evals en Phoenix (faithfulness, answer_relevancy y demás, con timestamp y commit SHA) para alimentar el dashboard de Calidad (observabilidad).
- [ ] Workflow `.github/workflows/eval.yml`: levanta Postgres como service, indexa corpus de prueba, ejecuta tests, comenta el PR con métricas, falla si threshold no se cumple.
- [ ] Comentario del PR con tabla de métricas comparada con la baseline de main.
- [ ] **Mitigación del free tier:** el gate del PR corre un subconjunto representativo del gold (~15 ejemplos, cubriendo los tipos) para no saturar los rate limits de Gemini en cada push. La suite completa (40 ejemplos) corre en un workflow programado nocturno (`schedule: cron`) o manual (`workflow_dispatch`), y actualiza la baseline de main.

## Acceptance criteria

- Push de un PR con regresión deliberada → el workflow bloquea el merge.
- Push de un PR con mejora → métricas reflejan la mejora.
- Comentario del PR legible con métricas actuales vs baseline.
- Tiempo total del workflow < 10 minutos en GitHub Actions.

## Riesgos

- Coste de evals en CI con Gemini Pro: cada PR consume tokens. Mitigado con el subconjunto en el gate del PR + suite completa nocturna; aun así, muchos PRs/día pueden rozar el rate limit. El workflow debe tener backoff y degradar con claridad si satura.
- Sesgo del juez (mismo proveedor): documentado en ADR-007.

## Preguntas abiertas

- ¿Snapshot testing del comportamiento entre versiones del modelo? Mencionar; implementación en v1.1.
