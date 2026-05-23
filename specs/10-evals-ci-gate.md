# Spec 10 · Evaluación + CI con gate del PR

**Estado:** aceptada
**Bloque:** E (Evaluación + CI)
**Dependencias:** Spec 08 (dataset gold), ADR-007 (RAGAS + Gemini Pro juez)

## Goal

Ejecutar el dataset gold contra el pipeline en cada PR, calcular métricas estándar de RAG con RAGAS, y bloquear el merge si caen por debajo del threshold.

## User story

> Como mantenedor, quiero que ningún PR se mergee si baja faithfulness, recall@5 u otra métrica clave. La regresión no debe llegar a main.

### Ubicación del código

El código de evals es un módulo de aplicación, no solo tests. Sigue el patrón de los demás dominios (`retrieval`, `chat`, `auth`):

- **Módulo:** `backend/app/evals/` con loader del gold, runner del pipeline, `metrics.py`, `thresholds.yaml`, `report.py`.
- **Tests:** `backend/tests/evals/test_pipeline.py` (parametrizados sobre el gold).

### Implementación

- [ ] `backend/app/evals/` loader que lee `corpus/sample/fastapi-docs/evals/gold.jsonl` y runner del pipeline.
- [ ] Métricas con RAGAS: `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`. Custom: `recall@5`, `MRR`.
- [ ] Juez: Gemini Pro (configurado en RAGAS). Generador del sistema sigue siendo Gemini Flash (ver ADR-007).
- [ ] Thresholds en `backend/app/evals/thresholds.yaml`. Los valores finales se fijan tras medir el baseline (ver gate más abajo); arranque orientativo: faithfulness ≥0.75, answer_relevancy ≥0.8, context_precision ≥0.7, context_recall ≥0.8, recall@5 ≥0.85, MRR ≥0.6.
- [ ] El runner registra cada ejecución en Phoenix (métricas, timestamp, commit SHA) para alimentar el dashboard de Calidad.
- [ ] Tests Pytest parametrizados en `backend/tests/evals/test_pipeline.py` que cargan el gold y ejecutan el pipeline; ~15 marcados `@pytest.mark.ci_subset` cubriendo todos los tipos del gold.
- [ ] Conectar el slash command `/eval` (`.claude/commands/eval.md`) al runner.

### Gate humano antes de cablear CI

El runner y los tests se implementan primero. Antes de cablear ningún workflow:

1. [ ] Medir baseline sobre `main` con un subset reducido (~8-10 ejemplos) para validar el flujo end-to-end sin agotar el free tier; generar `baseline_metrics.json`.
2. [ ] Proponer y acordar con el mantenedor **la estrategia del gate** a la luz del baseline: floor absoluto vs floor absoluto + regresión relativa contra el baseline de `main`, justificando el margen frente a la varianza del juez.
3. [ ] **Validar el juez** (Gemini Pro) con un spot-check humano de ~8 ejemplos del gold antes de confiarle el gate (ver ADR-007, notas).

### CI (tras aprobar la estrategia)

- [ ] `.github/workflows/eval.yml` (PR): levanta Postgres como service, indexa corpus de prueba, corre el subset (`ci_subset`), comenta el PR con tabla de métricas vs baseline de `main`, falla si no se cumple el threshold.
- [ ] `.github/workflows/eval-nightly.yml`: suite completa (40 ejemplos) en `schedule: cron` + `workflow_dispatch`, actualiza la baseline de `main`.
- [ ] Branch protection + secret `GOOGLE_API_KEY`.
- [ ] **Mitigación del free tier:** subset en el gate del PR; suite completa solo nocturna. Backoff y degradación clara si se satura el rate limit.

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
