# ADR-012: Gate de evaluación determinista por PR + juez LLM en la nocturna

**Estado:** aceptado
**Fecha:** 2026-05-23
**Tags:** evals, ci

## Contexto

El ADR-007 fija RAGAS con Gemini Pro como juez de calidad. Al cablear la evaluación a CI (Bloque E) surge una decisión nueva: **qué corre como gate bloqueante de cada PR y qué corre como monitor de tendencia**.

Medido sobre el free tier: el juez Gemini 3 Pro tarda ~50 s por llamada; el subset de CI con generación + juez se iba a 13-14 min y, con la cuota agotada, los runs expiraban (1 de 20 trabajos completó en 11 min). Un gate bloqueante con esa varianza y latencia hace el merge inviable y frágil.

## Drivers

- El gate del PR debe ser **rápido, determinista y reproducible** (no puede depender de la varianza de un LLM ni de la cuota del free tier).
- No queremos perder la señal de calidad de las métricas RAGAS (faithfulness, relevancy, precision, recall).
- Cero tarjeta: la cuota del juez es un recurso escaso.

## Opciones

- A. Gate del PR = solo métricas deterministas de retrieval (recall@5/MRR); juez RAGAS en una nocturna no bloqueante.
- B. Gate del PR = suite RAGAS completa con el juez (bloqueante).
- C. Sin gate por PR; solo nocturna.

## Decisión

Opción A. Dos workflows:

- **`eval.yml` (gate del PR, bloqueante):** solo deterministas — `recall@5`/`MRR` sobre los ejemplos answerable label-matchables de `CI_GATE_IDS`, excluyendo multi_source y `no_se`. Sin generación ni juez → corre en segundos. Floors recall@5/MRR ≥ 0.85. Es el check requerido en la protección de rama de `main`.
- **`eval-nightly.yml` (monitor de tendencia, NO bloquea PRs):** RAGAS + Gemini Pro sobre los 40 ejemplos, floors del juez + regresión absoluta (>0.07 vs baseline), refresca `baseline_metrics.json`. Un run rojo es una alerta de tendencia, no un bloqueo.

## Consecuencias

### Positivas

- Merge desbloqueado: el gate del PR corre en segundos y no depende del LLM ni de la cuota.
- Determinista y reproducible: el resultado del gate no varía entre ejecuciones.
- Se conserva la señal RAGAS como tendencia diaria sobre el dataset completo.

### Negativas

- El gate del PR no detecta regresiones de **generación** (faithfulness, etc.) en el momento del merge; se detectan con un día de retraso en la nocturna. Mitigación: la nocturna roja es alerta accionable; el retrieval (lo que sí gate-a) es la causa raíz más común de regresión de calidad.
- El match determinista por `(source, section)` es estricto; por eso multi_source queda como advisory.

## Notas

- El detector de abstención (`no_se`) sigue siendo frágil por marcadores de texto; un flag estructurado de abstención queda para v1.1.
- Si en el futuro se añade una segunda API con cuota holgada, reconsiderar incluir un subset del juez en el gate del PR.
