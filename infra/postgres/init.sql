-- Postgres bootstrap for the chatbot RAG vector store.
-- Runs once on first container start (empty data volume).
-- Tables are created by Alembic revisions (blocks B / CH / AU); this file only
-- guarantees the pgvector extension is available before any migration runs.

CREATE EXTENSION IF NOT EXISTS vector;
