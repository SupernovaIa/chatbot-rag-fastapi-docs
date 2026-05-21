# CLAUDE.md — Contexto del proyecto chatbot-rag-fastapi-docs

> Fichero leído por Claude Code y cualquier agente que abra este repo. Contiene el contexto mínimo del proyecto, las convenciones y cómo trabajar aquí.

## Qué es este proyecto

Chatbot RAG sobre las docs públicas de FastAPI. Caso práctico canónico de AI Engineering en producción: pipeline completo de indexación, retrieval híbrido con reranking, generación en streaming con citas y multi-turno, evaluación automática en CI con métricas estándar, observabilidad por query y defensa en capas frente a prompt injection.

Restricción transversal: **cero tarjeta**. Todo el stack se ejecuta en local con Docker; el único proveedor externo es Google AI Studio (free tier) para Gemini.

## Stack

- Backend: Python 3.12 + FastAPI + LangChain v1 + langchain-google-genai.
- Frontend: React + Vite.
- Vector store: Postgres 17 + pgvector 0.8+ (Docker).
- Object storage del corpus: Azurite emulando Azure Blob (Docker).
- Observabilidad: Phoenix self-host (Docker).
- Modelos: Gemini Flash (generación, reranker, guardrail), Gemini Pro (juez de evals), `gemini-embedding-001` 1536 dims (embeddings). Se fija el tier, no la versión; al construir se ancla el ID vigente con fecha. Default 2026-05-20: Gemini 3.5 Flash y Gemini 3 Pro. Requisito: free tier.
- Auth: FastAPI Users con email + password + bcrypt + JWT en cookie httpOnly.
- CI: GitHub Actions.

## Estructura del repo

```
.
├── backend/                    Backend Python (FastAPI)
│   ├── app/
│   │   ├── auth/               Auth con FastAPI Users
│   │   ├── chat/               Endpoint /chat, streaming, historial, caching
│   │   ├── indexing/           Loader, splitter, embeddings, schema pgvector
│   │   ├── retrieval/          Hybrid search, LLM-reranker, rewriter
│   │   ├── evals/              RAGAS, métricas, dataset gold runner
│   │   └── security/           Guardrails, filtros, rate limiting
│   ├── tests/                  Pytest con mocking de Gemini
│   └── migrations/             SQL migrations
├── frontend/                   Frontend React + Vite
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── pages/
├── corpus/sample/fastapi-docs/ Corpus pinned + dataset gold
│   ├── SOURCE.md               Origen, SHA, licencia
│   └── evals/gold.jsonl        40 ejemplos
├── prompts/                    System prompts versionados
├── scripts/                    upload_corpus.py, indexar.py
├── docs/
│   ├── adr/                    Architecture Decision Records (MADR)
│   └── architecture/           C4 model en Mermaid
├── specs/                      Specs de features (SDD ligero)
├── security/                   red-team-checklist.md
├── infra/                      docker-compose, configs
├── .claude/commands/           Slash commands del proyecto
├── .github/workflows/          CI workflows
├── CLAUDE.md                   Este fichero
├── CHANGELOG.md                Historial de cambios por bloque
├── SESSION.md                  Estado dinámico de la sesión actual
└── DECISIONS.md                Índice de ADRs
```

## Convenciones

### Idioma

- **Código en inglés siempre.** Variables, funciones, clases, comentarios, mensajes de log, nombres de ramas, mensajes de commit, paths de código.
- **Documentación en español neutro siempre.** README, ADRs, specs, diagramas C4, comentarios de PR, descripciones de issues. Sin voseo ni regionalismos.

### Git

- **Conventional Commits** desde el primer commit. `commitlint` aplicado en pre-commit.
- Ramas: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`. Una rama por bloque.
- PRs descritos en español, mensaje de commit en inglés.

### Flujo de gate y merge

- **El agente abre el PR y PARA.** No mergea ni crea tags: el merge y el tag `NN-block-<X>` son **acción humana** (es el gate de revisión). `main` está protegida.
- **Merges a `main` siempre en squash:** una entrada por bloque, coherente con un tag por bloque.
- **El flip de un bloque a `completado` en `SESSION.md` NO se hace con una PR aparte.** La siguiente sesión, como **primer commit de su rama**, marca el bloque anterior como `completado` y el nuevo como `in_progress`; ese cambio viaja en la PR del nuevo bloque. El **tag** `NN-block-<X>` es el registro duro de que el bloque quedó hecho.

### Dependencias

- **Backend Python con `uv`.** `pyproject.toml` para declarar deps, `uv.lock` committeado para builds reproducibles. Dockerfile con `uv sync --frozen`.
- **Frontend con npm.** `package-lock.json` committeado; CI usa `npm ci`.

### SDD ligero

- Antes de implementar una feature no trivial: spec en `specs/`. Estructura: goal, user story, approach, acceptance criteria, dependencies, risks.
- Antes de tomar una decisión arquitectónica: ADR en `docs/adr/`. Formato MADR (Markdown Architecture Decision Record).

### Arquitectura de código (ADR-011)

- **Package-by-feature**: `backend/app/<feature>/` (indexing, retrieval, chat, auth, evals, security, observability). Cada feature agrupa router, lógica y modelos.
- **Puertos finos para dependencias externas** (Gemini, pgvector, Azurite): interfaz (`Protocol`/ABC) + adaptador, para mockear en tests y poder cambiar de proveedor sin tocar la lógica.
- Sin capas domain/application/infrastructure ni DTOs/mappers (no es hexagonal puro). Wiring con `Depends` de FastAPI.

### Testing

- Backend: Pytest. Mockeo de llamadas a Gemini en tests unitarios. Tests de integración con Postgres y Azurite reales en CI.
- Frontend: sin tests automáticos en v1.0.0 (pendiente v1.1).

### Observabilidad

- Phoenix instrumentado desde el día uno. Cada llamada a Gemini y cada fase del pipeline emite un span.
- Logs en español o inglés a tu elección, mantener consistencia.
- PII redactada antes de loguear.

### Seguridad

- `.env` nunca commiteado. Solo `.env.example`.
- API keys vía variables de entorno o secrets de GitHub Actions.
- Defense in depth en 5 capas: safety filters de Gemini → guardrail Flash → system prompt robusto → filtro output → logging.

## Cómo trabajar aquí

1. Lee `SESSION.md` para saber el estado actual.
2. Lee la última entrada de `CHANGELOG.md` para ver qué se hizo en el bloque anterior.
3. Consulta `specs/` y `docs/adr/` según el bloque en curso.
4. Para abrir o cerrar una sesión: ver el runbook del kit de la lección L19.
5. Para correr el sistema: `docker compose up` desde la raíz.

## Comandos rápidos

```bash
# Levantar todo el stack
docker compose up

# Indexar el corpus
docker compose exec backend python scripts/indexar.py

# Correr evals
docker compose exec backend pytest tests/evals

# Acceder a Phoenix
open http://localhost:6006

# Acceder al frontend
open http://localhost:5173
```

## Referencias

- Guía de la lección: `agentic-development/guias/modulo-6/leccion-19/`.
- Brief técnico: `agentic-development/guias/modulo-6/leccion-19/brief.md`.
- Plan de construcción: `agentic-development/guias/modulo-6/leccion-19/PLAN.md`.
