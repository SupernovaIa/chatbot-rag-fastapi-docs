# chatbot-rag-fastapi-docs

Chatbot RAG sobre las docs públicas de FastAPI. Caso práctico canónico de AI
Engineering en producción: indexación, retrieval híbrido con reranking,
generación en streaming con citas y multi-turno, evaluación automática en CI,
observabilidad por query y defensa en capas frente a prompt injection.

Restricción transversal: **cero tarjeta**. Todo el stack corre en local con
Docker; el único proveedor externo es Google AI Studio (free tier) para Gemini.

## Stack

- **Backend:** Python 3.12 + FastAPI + LangChain v1 + langchain-google-genai.
- **Frontend:** React + Vite + TypeScript.
- **Vector store:** Postgres 17 + pgvector 0.8+.
- **Object storage:** Azurite (emulador de Azure Blob).
- **Observabilidad:** Phoenix self-host.
- **CI:** GitHub Actions.

## Requisitos

- Docker + Docker Compose.
- Para desarrollo del backend fuera de Docker: [uv](https://docs.astral.sh/uv/).
- Para los hooks de git: Node.js 20+.

## Quickstart

```bash
# 1. Configura el entorno
cp .env.example .env
#    rellena GOOGLE_API_KEY y JWT_SECRET en .env

# 2. Instala los git hooks (husky + commitlint)
npm install

# 3. Levanta el stack completo
docker compose up -d
```

Cuando los cinco servicios estén sanos:

| Servicio | URL |
|---|---|
| Frontend (Vite) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000/health |
| Phoenix | http://localhost:6006 |
| Postgres + pgvector | localhost:5432 |
| Azurite (Blob) | localhost:10000 |

```bash
# Comprobar estado de los servicios
docker compose ps

# Health del backend
curl http://localhost:8000/health
```

## Estructura

```
backend/    FastAPI (package-by-feature), tests, Alembic
frontend/   React + Vite + TS
infra/      postgres/init.sql y config de soporte
corpus/     corpus pinned + dataset gold (bloques posteriores)
prompts/    system prompts versionados
scripts/    utilidades (upload_corpus, indexar)
security/   red-team checklist
docs/       ADRs (MADR) y modelo C4
specs/      specs de features (SDD ligero)
```

## Convenciones

- **Conventional Commits** validados por commitlint en el hook `commit-msg`.
- Código en inglés; documentación en español neutro.
- Detalle en `CLAUDE.md` y en `docs/adr/`.
