# Corpus: FastAPI Official Documentation

## Origen

- **Repositorio:** https://github.com/tiangolo/fastapi
- **Tag:** 0.115.0
- **Commit SHA:** 40e33e492dbf4af6172997f4e3238a32e56cbe26
- **Fecha snapshot:** 2026-05-21
- **Ruta fuente:** `docs/en/docs/`
- **Licencia:** MIT (https://github.com/tiangolo/fastapi/blob/master/LICENSE)

## Contenido

144 ficheros Markdown (.md) exportados de la documentación oficial de FastAPI v0.115.0.
Incluye la guía principal, tutoriales, referencia avanzada y guía de despliegue.

## Corpus SHA

El corpus_sha utilizado para la idempotencia de indexación es el SHA del commit de origen:
```
40e33e492dbf4af6172997f4e3238a32e56cbe26
```

## Reproducir el snapshot

```bash
git clone --depth 1 --filter=blob:none --sparse --branch 0.115.0 \
  https://github.com/tiangolo/fastapi /tmp/fastapi-snapshot
cd /tmp/fastapi-snapshot
git sparse-checkout set docs/en/docs
cp -r docs/en/docs/ corpus/sample/fastapi-docs/
```
