---
description: Conduce un evolutivo brownfield sobre el sistema congelado: leer diseño → ubicar el cambio → spec/ADR → implementar → verificar pronto → PR y parar (gate humano)
---

Conduce un **evolutivo brownfield** sobre este repo ya congelado (v1.0.0+), encapsulando el ritual de leer el diseño existente antes de tocar nada, escribir la spec apoyándose en él, implementar, verificar pronto y parar en el gate humano.

El argumento es la descripción del evolutivo (qué se quiere añadir/cambiar). Si no se da, pídela y espera respuesta antes de seguir: `$ARGUMENTS`

Ejecuta estas fases **en orden**. No saltes a implementar sin haber ubicado el cambio y escrito la spec.

## Fase 1 — Leer el diseño existente

1. Lee `SESSION.md` (estado actual) y la última entrada de `CHANGELOG.md`.
2. Identifica el/los feature(s) afectados en `backend/app/<feature>/` y/o `frontend/src/`.
3. Lee lo relevante para el cambio, no el repo entero: el router/store/modelos del feature, sus specs en `specs/`, los ADRs aplicables en `docs/adr/` (especialmente **ADR-011**, arquitectura de código) y migraciones si toca el esquema.

## Fase 2 — Ubicar el cambio

Resume en **un párrafo** dónde encaja el cambio: qué ficheros, qué patrón existente se reusa (simetría con código ya presente), y qué restricciones aplican (puertos finos del ADR-011, FKs/cascade, scoping por usuario, etc.). Señala explícitamente los riesgos detectados en el diseño actual. **Para y enséñaselo al usuario** antes de escribir spec.

## Fase 3 — Marcar SESSION.md y abrir rama

Como **primer commit de la rama nueva** (`feat/<slug>`, `fix/<slug>`, etc.):
- Marca el bloque anterior como `completado` y abre el evolutivo como `in_progress` en `SESSION.md` (bloque/estado/fechas/objetivo/próxima acción).
- Commit `chore(session): open <bloque> (<descripción>)`.

## Fase 4 — Spec (y ADR solo si hay decisión)

- Escribe una **spec corta** en `specs/NN-<slug>.md` con: estado, bloque, dependencias, goal, user story, approach (checklist), acceptance criteria, tests, risks.
- **ADR solo si hay una decisión arquitectónica que tomar** (alternativas con trade-offs). Si el cambio es simétrico a algo ya existente y no hay decisión, indícalo en la spec y **no** crees ADR.
- Si la decisión no es trivial o hay alternativas reales, propón las opciones al usuario y espera.

## Fase 5 — Implementar y verificar PRONTO

- Implementa respetando el ADR-011 (package-by-feature, puertos finos, wiring con `Depends`) y las convenciones de `CLAUDE.md` (código en inglés, docs en español).
- **Verifica en cuanto exista lo mínimo verificable, no al cerrar.** Para un endpoint: pruébalo en vivo (`curl`, varios usuarios si hay scoping) y enseña los casos clave (happy path + errores: 403/404/...) **antes** de seguir con capas dependientes (p. ej. frontend). Si el contenedor no tiene bind-mount del código, reconstrúyelo (`docker compose up -d --build backend`) o copia los ficheros al contenedor para correr tests (`docker cp` + `pytest`).
- Añade tests del cambio (backend: Pytest con Gemini mockeado).

## Fase 6 — Commits divididos, PR y PARAR

- **Commits divididos por unidad lógica** (Conventional Commits, sin atribución de IA): p. ej. la feature en un commit y herramientas/tooling auxiliares en otro.
- Abre el PR (descripción en español, commits en inglés) y **PARA**.
- **No mergees ni crees tags.** El merge en squash y el tag `NN-block-<X>` son acción humana (el gate de revisión). `main` está protegida.
