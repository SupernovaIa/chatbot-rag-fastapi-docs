# ADR-005: Multi-turn con sliding window de N=5

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** chat, retrieval, history

## Contexto

El chatbot mantiene conversaciones multi-turno. El historial pasado al pipeline (para query rewriting y para el prompt del generador) tiene que estar acotado: ni demasiado corto (chatbot amnésico) ni demasiado largo (coste alto, "lost in the middle").

## Drivers

- Latencia y coste por turno bajo control.
- Continuidad conversacional aceptable.
- Implementación simple en v1.0.

## Opciones

- A. Sliding window de N turnos fijos.
- B. Resumen rolling del historial cuando crece.
- C. Embedding del historial y retrieval semántico del contexto pasado.

## Decisión

Opción A con N=5. Los 5 turnos más recientes se cargan en cada query; los anteriores no se borran (siguen en BBDD) pero no se incluyen en el prompt.

## Consecuencias

### Positivas

- Implementación trivial.
- Predecible.
- Coste por turno acotado.

### Negativas

- En conversaciones muy largas se pierde contexto temprano.

## Alternativas descartadas

- Resumen rolling: añade una llamada LLM extra por turno. Documentado como evolución para v1.1.
- Retrieval semántico del historial: complejidad alta para beneficio marginal en v1.0.

## Justificación de N=5

- N=1 a 3: pierde contexto demasiado pronto, chatbot percibido como olvidadizo.
- N=10+: tokens crecen, coste y latencia suben, "lost in the middle" empieza a degradar reescritura.
- N=5 cubre el ~90% de conversaciones de soporte sin saturar contexto.
