# Azurite local setup

## Connection string de desarrollo

Azurite expone una cuenta de almacenamiento de desarrollo fija. **No son secretos de producción.**

> ⚠️ La `AccountKey` varía según la versión de la imagen Azurite. Comprueba siempre
> el valor real con:
> ```bash
> docker compose exec azurite grep -r "EMULATOR_ACCOUNT_KEY_STR" /opt/azurite/dist/src/blob/utils/constants.js
> ```

La clave para la imagen `mcr.microsoft.com/azure-storage/azurite:latest` (verificada 2026-05-21):

```
DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
```

> Nota: la documentación antigua de Microsoft muestra `...KgdSF74YxZDQ==` (clave histórica);
> versiones recientes de Azurite usan `...KBHBeksoGMGw==`.

Referencia oficial (puede estar desactualizada):
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
