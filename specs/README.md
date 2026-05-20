# Specs

Especificaciones de las features del proyecto. Cada spec define **qué** construir en una feature concreta: objetivo, user story, approach, criterios de aceptación, riesgos y preguntas abiertas. Junto con los ADRs (`../docs/adr/`) y los diagramas C4 (`../docs/architecture/`) forman el diseño base sobre el que se construye.

Las specs son la fuente de verdad de la implementación: cada bloque de construcción implementa contra la spec correspondiente y verifica sus criterios de aceptación.

| Spec | Feature | Bloque que la implementa |
|---|---|---|
| [01](01-indexacion.md) | Indexación del corpus | B |
| [02](02-hybrid-search.md) | Búsqueda híbrida con RRF | R |
| [03](03-llm-reranker.md) | LLM-as-reranker (RankGPT) | R |
| [04](04-multi-turn-rewriting.md) | Query rewriting multi-turn | R |
| [05](05-chat-endpoint.md) | Endpoint /chat con streaming SSE | CH |
| [06](06-history-management.md) | Gestión de historial multi-turn | CH |
| [07](07-context-caching.md) | Gemini context caching (implícito) | CH |
| [08](08-dataset-gold.md) | Dataset gold de evaluación | G |
| [09](09-security-layers.md) | Defense in depth en 5 capas | S |
| [10](10-evals-ci-gate.md) | Evaluación + CI con gate del PR | E |

Una spec nueva (o un cambio sustancial) se redacta y revisa antes de implementar.
