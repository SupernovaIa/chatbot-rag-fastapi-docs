# Backend — chatbot RAG

Backend FastAPI del chatbot RAG sobre las docs de FastAPI. Arquitectura
package-by-feature con puertos finos para dependencias externas (ver
`docs/adr/ADR-011-arquitectura-codigo.md`).

## Desarrollo local

```bash
uv sync                       # instala dependencias
uv run uvicorn app.main:app --reload
uv run pytest                 # tests
uv run alembic upgrade head   # aplica migraciones
```

El stack completo (Postgres, Azurite, Phoenix, frontend) se levanta con
`docker compose up -d` desde la raíz del repo.
