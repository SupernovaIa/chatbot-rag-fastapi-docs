# chatbot-rag-fastapi-docs

Chatbot RAG sobre la documentación pública de FastAPI. Caso práctico canónico
de AI Engineering en producción: pipeline completo de indexación, retrieval
híbrido con reranking, generación en streaming con citas y multi-turno,
evaluación automática en CI con métricas estándar, observabilidad por query y
defensa en capas frente a prompt injection.

**Restricción transversal: cero tarjeta.** Todo el stack corre en local con
Docker; el único proveedor externo es Google AI Studio (free tier) para Gemini.

## Qué es

Le preguntas en lenguaje natural sobre FastAPI y responde con el texto de la
documentación oficial, citando las fuentes `[1] [2]` que el frontend resuelve a
chips clicables. Cada turno recorre el pipeline RAG (reescritura multi-turn →
retrieval híbrido denso + BM25 con fusión RRF → reranking con LLM → generación
en streaming con caching implícito), se evalúa contra un dataset gold revisado a
mano y emite trazas por fase a Phoenix. Las conversaciones son privadas por
usuario (auth con JWT en cookie httpOnly) y el endpoint está protegido por cinco
capas de defensa frente a inyección de prompts y fuga de información.

Es un proyecto **didáctico de referencia**, no un SaaS: el objetivo es mostrar
las piezas de un RAG productivo extremo a extremo bajo una restricción real
(sin coste de infraestructura).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 · FastAPI · LangChain v1 · langchain-google-genai |
| Frontend | React · Vite · TypeScript (nginx en build de producción) |
| Vector store | Postgres 17 + pgvector 0.8+ (HNSW + GIN para BM25) |
| Object storage | Azurite (emulador de Azure Blob) |
| Observabilidad | Arize Phoenix self-host (OpenTelemetry / OpenInference) |
| Modelos | Gemini Flash (generación, reranker, guardrail) · Gemini Pro (juez de evals) · `gemini-embedding-001` 1536 dims |
| Auth | FastAPI Users · email + password + bcrypt · JWT en cookie httpOnly |
| Evals | RAGAS con Gemini Pro como juez + métricas deterministas |
| CI | GitHub Actions (gate de eval por PR + nocturna de calidad) |
| Gestión deps | `uv` (backend) · `npm` (frontend) |

Los IDs de modelo se anclan con fecha (ADR-001). Default 2026-05-20: Gemini 3.5
Flash y Gemini 3 Pro.

## Requisitos

- Docker + Docker Compose.
- Una `GOOGLE_API_KEY` de [Google AI Studio](https://aistudio.google.com/) (free tier).
- Node.js 20+ para los git hooks (husky + commitlint).
- `uv` solo si vas a desarrollar el backend fuera de Docker.

## Quickstart (5 pasos)

```bash
# 1. Clona el repositorio
git clone <url-del-repo> chatbot-rag-fastapi-docs
cd chatbot-rag-fastapi-docs

# 2. Configura el entorno
cp .env.example .env
#    Rellena GOOGLE_API_KEY y pon un JWT_SECRET largo y aleatorio.
npm install          # instala los git hooks (commitlint)

# 3. Levanta el stack completo (5 servicios)
docker compose up -d
#    Espera a que estén "healthy":  docker compose ps

# 4. Indexa el corpus (migraciones → subir a Azurite → embeddings → pgvector)
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/upload_corpus.py --corpus-dir /corpus/sample/fastapi-docs
docker compose exec backend python scripts/index_corpus.py

# 5. Abre el frontend
open http://localhost:5173      # regístrate, inicia sesión y pregunta
```

Servicios y puertos una vez sano el stack:

| Servicio | URL |
|---|---|
| Frontend (Vite dev) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000/health |
| Phoenix (trazas) | http://localhost:6006 |
| Postgres + pgvector | localhost:5432 |
| Azurite (Blob) | localhost:10000 |

Para servir el frontend de producción (nginx + proxy a `/api`):
`docker compose --profile prod up -d frontend-prod` → http://localhost:80.

## Evaluación y red teaming

**Evals** — corre el dataset gold (40 ejemplos revisados a mano) contra el
pipeline y reporta métricas. Hay dos modos:

```bash
# Gate determinista (rápido, sin juez ni generación): recall@5 / MRR
docker compose exec backend python -m app.evals.cli --subset ci_subset --retrieval-only

# Suite completa con juez RAGAS (Gemini Pro): faithfulness, relevancy, precision, recall
docker compose exec backend python -m app.evals.cli --subset full
```

En CI: `eval.yml` corre el gate determinista por PR (bloqueante, en segundos) y
`eval-nightly.yml` corre la suite completa con el juez como monitor de tendencia
no bloqueante (ADR-012).

**Red teaming** — lanza la checklist de 20 prompts hostiles (incluye inyección
indirecta plantando chunks envenenados en pgvector) contra el sistema real y
reporta el block rate:

```bash
docker compose exec backend python scripts/red_team.py \
  --database-url postgresql+psycopg://postgres:postgres@postgres:5432/chatbot_rag
# Gate: >= 18/20 bloqueados, >= 3 de inyección indirecta neutralizada, 0 fugas.
# (--database-url solo se usa para plantar/limpiar los chunks de inyección indirecta.)
```

Los slash commands `/eval` y `/redteam` envuelven estos scripts y cruzan los
resultados con los spans de Phoenix.

## Estructura del repo

```
.
├── backend/                    Backend Python (FastAPI, package-by-feature)
│   ├── app/
│   │   ├── auth/               Auth con FastAPI Users (JWT cookie, scoping)
│   │   ├── chat/               Endpoint /chat, streaming SSE, historial, citas
│   │   ├── indexing/           Loader, splitter, embeddings, schema pgvector
│   │   ├── retrieval/          Híbrido + RRF, LLM-reranker, rewriter multi-turn
│   │   ├── evals/              RAGAS, métricas, gold runner, gate
│   │   ├── security/           Guardrail, filtro output, incidentes, rate limit
│   │   └── observability/      Tracing OTel → Phoenix, modelo de coste
│   ├── tests/                  Pytest (Gemini mockeado en unitarios)
│   └── migrations/             Migraciones Alembic
├── frontend/                   React + Vite + TS (dev y build nginx)
├── corpus/sample/fastapi-docs/ Corpus pinned (SHA) + dataset gold (40 ej.)
├── prompts/                    System prompts versionados
├── scripts/                    upload_corpus, index_corpus, red_team, validate_gold
├── docs/
│   ├── adr/                    Architecture Decision Records (MADR, 12)
│   └── architecture/           Modelo C4 (contexto, contenedores, pipeline, componentes)
├── specs/                      Specs de features (SDD ligero)
├── security/                   Red-team checklist + resultados
├── infra/                      docker-compose support, dashboards Phoenix
└── .github/workflows/          CI (gate de eval por PR + nocturna)
```

Contexto completo de trabajo y convenciones en `CLAUDE.md`; decisiones en
`DECISIONS.md` y `docs/adr/`; estado de la última sesión en `SESSION.md`.

## Roadmap v1.1

Evolutivo sobre la base v1.0.0:

- **Borrar conversaciones**: gestión del ciclo de vida del historial por el
  usuario (borrado de sesiones y mensajes, con scoping y soft-delete).
- **Retrieval gating**: decidir _si_ recuperar antes de recuperar — saltar el
  pipeline en preguntas que no lo necesitan (saludos, meta-preguntas) para
  ahorrar latencia y cuota, y abstenerse mejor cuando no hay contexto relevante.

Deuda registrada para más adelante: tests automáticos de frontend, ampliar la
cobertura del dataset gold (`advanced/`, `how-to/`, OAuth2), flag estructurado
de abstención, y PII más allá de regex (p. ej. Presidio).

## Anexo: despliegue en Azure (guía, no implementado en v1.0)

El stack está diseñado **emulator-first** para migrar a Azure sin reescribir la
lógica de aplicación. Esta sección es orientativa; v1.0.0 corre íntegramente en
local con Docker.

- **Object storage**: Azurite emula Azure Blob con el mismo SDK
  (`azure-storage-blob`). En Azure, sustituye la connection string del emulador
  por la de una cuenta de **Azure Blob Storage** real; el código del loader no
  cambia.
- **Vector store**: migra de Postgres+pgvector en contenedor a **Azure Database
  for PostgreSQL Flexible Server** con la extensión `pgvector` habilitada. Mismo
  `DATABASE_URL`, distinto host y credenciales gestionadas.
- **Backend/Frontend**: empaqueta las imágenes existentes en **Azure Container
  Apps** (o App Service for Containers). El build de producción del frontend
  (nginx) ya está preparado.
- **Secretos**: mueve `GOOGLE_API_KEY` y `JWT_SECRET` a **Azure Key Vault**;
  fija `ENVIRONMENT=production` (fuerza JWT_SECRET real y cookies Secure) y
  restringe `CORS_ORIGINS` al dominio del frontend.
- **Observabilidad**: Phoenix puede correr como contenedor propio o exportar
  OTLP a un colector gestionado.

## Licencia y corpus

El corpus es un snapshot pinned de la documentación de FastAPI (ver
`corpus/sample/fastapi-docs/SOURCE.md` para origen, SHA y licencia).
