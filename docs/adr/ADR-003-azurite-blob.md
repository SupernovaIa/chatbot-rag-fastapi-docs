# ADR-003: Azurite como object storage del corpus

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** storage, infrastructure

## Contexto

El corpus de FastAPI docs vive como Markdown. En producción real estaría en object storage (S3, GCS, Azure Blob). Para que el alumno aprenda el patrón "código idéntico local/prod", el corpus en dev también debe vivir en object storage emulado.

## Drivers

- Patrón "emulator-first" de Azure dev.
- Cero tarjeta.
- Mismo SDK en dev y prod (cambiar solo connection string).

## Opciones

- A. Azurite (emulador oficial de Azure Storage).
- B. MinIO (emulador S3).
- C. Filesystem local, sin object storage.

## Decisión

Opción A. Azurite en Docker emulando Azure Blob. SDK `azure-storage-blob` apunta a Azurite vía connection string. En producción, mismo código apunta a Azure Blob real.

## Consecuencias

### Positivas

- Código idéntico local y producción.
- Curva de aprendizaje del SDK reutilizable.
- Encaja con el anexo Azure (v1.1.0).

### Negativas

- Azurite solo emula Blob, Queue, Table. No emula Azure AI Search.
- El alumno aprende el SDK de Azure, no de AWS/GCS. Sesgo Microsoft asumido.

## Alternativas descartadas

- MinIO: válido si el alumno fuera a AWS S3. En este caso vamos a Azure para el anexo, así que Azurite alinea mejor.
- Filesystem: pierde el patrón object storage que es estándar en producción.
