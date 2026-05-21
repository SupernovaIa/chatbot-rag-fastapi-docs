# Dataset gold de evaluación

Dataset curado y firmado a mano de 40 ejemplos en español sobre el corpus de
FastAPI docs (en inglés), usado como referencia para la evaluación automática
del pipeline RAG. Ver `specs/08-dataset-gold.md`.

## Ficheros

- `gold.jsonl` — un ejemplo por línea (JSON Lines).

## Schema por ejemplo

| Campo                | Tipo            | Descripción                                                                 |
|----------------------|-----------------|-----------------------------------------------------------------------------|
| `id`                 | string          | Identificador estable. Formato `g-<NN>`.                                     |
| `type`               | string          | Uno de: `factual`, `paraphrase`, `multi_source`, `no_se`, `multi_turn`.     |
| `question_es`        | string          | Pregunta del usuario, en español.                                           |
| `expected_answer_es` | string          | Respuesta esperada, en español (puede citar términos en inglés del corpus). |
| `gold_chunks`        | array de objeto | Chunks relevantes; cada uno `{source, section}`. Vacío para `no_se`.        |
| `notes`              | string          | Notas del anotador (intención, matices, por qué es difícil).                |
| `reviewed_by`        | string          | Quién firmó el ejemplo. Obligatorio (`javi`).                               |
| `reviewed_at`        | string (date)   | Fecha de la firma, `YYYY-MM-DD`. Obligatorio.                               |
| `previous_turns`     | array de objeto | Solo `multi_turn`: turnos previos `{question_es, answer_es}`.               |

### `gold_chunks`

Cada chunk referencia una sección del corpus por su par `source` (path relativo
dentro de `corpus/sample/fastapi-docs/`) y `section` (jerarquía de cabeceras
Markdown, p. ej. `Path Parameters > Path parameters with types`). Estos valores
coinciden con los metadatos `metadata->>'source'` y `metadata->>'section'` de la
tabla `chunks` en pgvector.

### Ejemplos `no_se`

`gold_chunks` vacío y `expected_answer_es` con la frase de rechazo esperada: el
sistema no debe inventar respuesta cuando la pregunta cae fuera del corpus.

## Distribución (40 ejemplos)

| Tipo           | Cantidad |
|----------------|----------|
| `factual`      | 15       |
| `paraphrase`   | 8        |
| `multi_source` | 7        |
| `no_se`        | 5        |
| `multi_turn`   | 5        |

## Validación

```bash
python scripts/validate_gold.py
```

Verifica: parseo JSONL, schema, distribución, firma de cada ejemplo y que todos
los `gold_chunks` existan en pgvector con el `corpus_sha` actual.
