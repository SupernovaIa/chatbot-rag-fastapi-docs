# Makefile — atajos para el stack local del chatbot RAG.
#
# Requisitos: Docker + docker compose plugin (v2).
#
# Uso:
#   make dev    Levanta el stack completo en modo desarrollo (Vite :5173)
#   make prod   Levanta el stack con el build de producción nginx (:80)
#   make down   Para todos los servicios y elimina los contenedores

.PHONY: dev prod down

## Levanta postgres, azurite, phoenix, backend y frontend dev (Vite :5173).
dev:
	docker compose up

## Levanta el stack completo con el build de producción (nginx :80).
## Siempre reconstruye el bundle de Vite antes de arrancar nginx.
prod:
	docker compose --profile prod up --build

## Para todos los servicios y elimina los contenedores (los volúmenes se conservan).
down:
	docker compose down
