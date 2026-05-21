# Azurite local setup

## Connection string de desarrollo

Azurite expone una cuenta de almacenamiento de desarrollo fija con credenciales públicas documentadas por Microsoft. **No son secretos de producción.**

Para `AZURE_STORAGE_CONNECTION_STRING` en el `.env` local:

```
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=<ver abajo>;BlobEndpoint=http://azurite:10000/devstoreaccount1;
```

La `AccountKey` del emulador es la clave de desarrollo bien conocida de Azurite.
Encuéntrala en la documentación oficial de Microsoft:
https://learn.microsoft.com/azure/storage/common/storage-use-azurite#well-known-storage-account-and-key

Para scripts corriendo **fuera** del Docker (ej. `python scripts/upload_corpus.py` desde el host):
- Cambia `BlobEndpoint=http://azurite:10000/devstoreaccount1` por `http://127.0.0.1:10000/devstoreaccount1`.

## Verificar que Azurite está arriba

```bash
docker compose exec azurite nc -z 127.0.0.1 10000 && echo "ok"
```

## Flujo completo (Bloque B)

```bash
# 1. Levantar stack
docker compose up -d

# 2. Aplicar migración de la tabla chunks
docker compose exec backend alembic upgrade head

# 3. Subir corpus desde el host
python scripts/upload_corpus.py

# 4. Indexar (requiere GOOGLE_API_KEY en .env)
docker compose exec backend python scripts/index_corpus.py

# 5. Verificar COUNT
docker compose exec postgres psql -U postgres -d chatbot_rag \
  -c "SELECT COUNT(*), corpus_sha FROM chunks GROUP BY corpus_sha;"
```
