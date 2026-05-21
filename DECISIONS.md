# Decisiones de arquitectura (ADR)

Índice de los Architecture Decision Records del proyecto. Cada ADR registra una decisión técnica con su contexto, alternativas consideradas y consecuencias. Forman, junto con las specs y los diagramas C4, el diseño base del proyecto.

| ADR | Decisión | Estado | Fecha |
|---|---|---|---|
| [ADR-001](docs/adr/ADR-001-stack.md) | Stack del proyecto bajo restricción cero tarjeta | aceptado | 2026-05-20 |
| [ADR-002](docs/adr/ADR-002-pgvector.md) | Postgres + pgvector como vector store | aceptado | 2026-05-20 |
| [ADR-003](docs/adr/ADR-003-azurite-blob.md) | Azurite como object storage del corpus | aceptado | 2026-05-20 |
| [ADR-004](docs/adr/ADR-004-llm-reranker.md) | LLM-as-reranker (RankGPT) vs cross-encoder dedicado | aceptado | 2026-05-20 |
| [ADR-005](docs/adr/ADR-005-sliding-window-n5.md) | Multi-turn con sliding window de N=5 | aceptado | 2026-05-20 |
| [ADR-006](docs/adr/ADR-006-auth-basica.md) | Autenticación con FastAPI Users (email + password + JWT) | aceptado | 2026-05-20 |
| [ADR-007](docs/adr/ADR-007-ragas-gemini-juez.md) | RAGAS con Gemini Pro como juez de evaluación | aceptado | 2026-05-20 |
| [ADR-008](docs/adr/ADR-008-phoenix-observability.md) | Arize Phoenix self-host como observabilidad | aceptado | 2026-05-20 |
| [ADR-009](docs/adr/ADR-009-frontend-separado.md) | Frontend React + Vite en contenedor separado | aceptado | 2026-05-20 |
| [ADR-010](docs/adr/ADR-010-langchain-v1.md) | LangChain v1 + langchain-google-genai como framework | aceptado | 2026-05-20 |
| [ADR-011](docs/adr/ADR-011-arquitectura-codigo.md) | Arquitectura de código: package-by-feature + puertos para dependencias externas | aceptado | 2026-05-21 |

Las decisiones que surjan durante la construcción se añaden aquí como nuevos ADRs.
