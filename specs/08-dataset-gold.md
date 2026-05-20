# Spec 08 · Dataset gold de evaluación

**Estado:** aceptada
**Bloque:** G (Dataset gold)
**Dependencias:** Spec 01 (corpus indexado)

## Goal

Construir un dataset gold de 40 ejemplos en español sobre el corpus de FastAPI docs (en inglés), curado y firmado a mano, que sirva de referencia para evaluación automática.

## User story

> Como operador, quiero un set de 40 preguntas anotadas con respuesta esperada y chunks gold, que puedo correr contra el pipeline para obtener métricas reproducibles.

## Approach

- [ ] Ubicación: `corpus/sample/fastapi-docs/evals/gold.jsonl`.
- [ ] Distribución: 15 factuales, 8 paráfrasis, 7 multi-fuente, 5 "no sé", 5 multi-turn (pares).
- [ ] Schema por ejemplo: `id`, `type`, `question_es`, `expected_answer_es`, `gold_chunks` (paths con secciones), `notes`, `reviewed_by`, `reviewed_at`.
- [ ] Multi-turn lleva campo extra `previous_turns: [{question_es, answer_es}, ...]`.
- [ ] El agente genera borradores leyendo el corpus indexado, propone uno a uno.
- [ ] Tú revisas cada ejemplo, ajustas, firmas. No se acepta ejemplo sin firma.
- [ ] Script `scripts/validate_gold.py` que verifica que todos los `gold_chunks` existen en pgvector con el SHA actual.

## Acceptance criteria

- `gold.jsonl` con 40 entradas válidas (parseables, schema cumplido).
- `scripts/validate_gold.py` pasa sin errores.
- Cada ejemplo tiene `reviewed_by` y `reviewed_at` rellenos.
- Distribución cumple los porcentajes acordados.

## Riesgos

- Generación con LLM puede dar ejemplos "fáciles" sesgados. Mitigar con revisión humana obligatoria.
- Cambio del SHA del corpus invalida `gold_chunks`. Mitigar con el script de validación.

## Preguntas abiertas

- ¿Idioma del `expected_answer_es`? Default español, aunque cite contenido en inglés del corpus.
- ¿Cómo manejamos los ejemplos "no sé"? `gold_chunks` vacío, `expected_answer_es` con la frase de rechazo esperada.
