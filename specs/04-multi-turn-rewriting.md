# Spec 04 · Query rewriting multi-turn

**Estado:** aceptada
**Bloque:** R (Retrieval modular)
**Dependencias:** ADR-005 (sliding window N=5). Spec 06 (historial) **solo como contrato de datos**: el rewriter recibe `history: list[Turn]` como parámetro. En el bloque R se construye y testea con historial sintético; la persistencia del historial llega en el bloque CH (Spec 06), que es posterior. No hay dependencia de implementación, solo de la forma de `Turn`.

## Goal

Convertir la query actual del usuario en una pregunta independiente ("standalone question") usando el historial conversacional, para que retrieval funcione bien en multi-turn.

## User story

> Como usuario, cuando pregunto "¿y cómo lo desactivo?" después de haber hablado de 2FA, quiero que el sistema entienda que pregunto por "cómo desactivar 2FA en mi cuenta".

## Approach

- [ ] Prompt del rewriter en `prompts/rewriter.md`, versionado.
- [ ] Entrada: últimos N=5 turnos del historial + query actual.
- [ ] Salida: query reescrita como standalone question.
- [ ] Si la query ya es independiente (no contiene referencias anafóricas, primer turno, etc.), el rewriter la devuelve igual.
- [ ] Solo la query reescrita va al embedding y al retrieval; el generador final recibe la query original + historial completo + chunks.

## Acceptance criteria

- `rewrite_query(query: str, history: list[Turn]) -> str`.
- Test: primer turno, query original = query reescrita.
- Test: query con referencia anafórica, reescrita resuelve la referencia.
- Test: history vacío, query original = query reescrita.
- Latencia p50 < 1.5s.
- Trazas Phoenix muestran fase `rewrite` con `original_query`, `rewritten_query`, `history_turns_used`.

## Riesgos

- Rewriter puede sobre-reescribir y perder matices. Mitigar con ejemplos en el prompt.
- Coste extra por turno (una llamada LLM). En free tier no es problema; documentar para producción.

## Preguntas abiertas

- ¿Qué hacer si el rewriter falla? Default: usar query original con log de warning.
