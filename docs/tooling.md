# Herramientas de desarrollo agéntico

Este proyecto se construye con **Claude Code** de forma disciplinada (una sesión = una fase = un gate de revisión). Estas son las piezas del entorno que se usan.

## MCPs (`.mcp.json`)

Servidores que el agente carga al abrir el repo.

| MCP | Para qué |
|---|---|
| **Postgres** | Inspeccionar pgvector, ejecutar queries de retrieval a mano, comprobar metadatos de los chunks. |
| **Context7** | Documentación actualizada y version-specific de LangChain, FastAPI, pgvector, etc., inyectada en contexto para no alucinar APIs. |

GitHub no usa MCP: las operaciones (PRs, Actions, secrets) van por el `gh` CLI.

## Skills

Las skills son capacidades transversales de Claude Code. Este proyecto **no crea skills propias**; usa las disponibles en el entorno.

| Skill | Origen | Cuándo se usa |
|---|---|---|
| `commit` | built-in | Al cerrar cada unidad lógica. |
| `review` | built-in | Gate de revisión de cada PR antes de mergear. |
| `security-review` | built-in | Antes de cerrar la fase de seguridad y antes del release. |
| `simplify` | built-in | Sobre el código tocado al final de cada fase. |
| `fewer-permission-prompts` | built-in | Tras varias sesiones, para afinar la allowlist de permisos. |
| `ui-ux-pro-max` | personal (no incluida en el repo) | Opcional en el frontend; el estilo lo fija `docs/design-system.md`. |

Las cinco built-in vienen con Claude Code. `ui-ux-pro-max` es una skill personal de terceros; no se versiona aquí, y el diseño del frontend no depende de ella (la fuente de estilo es `docs/design-system.md`).

## Slash commands del proyecto (`.claude/commands/`)

Operaciones repetibles, específicas de este repo. Se conectan a sus módulos durante la construcción.

| Comando | Qué hace |
|---|---|
| `/index` | Ejecuta el pipeline de indexación del corpus. |
| `/retrieve` | Lanza una query de retrieval manual para inspección. |
| `/eval` | Corre el dataset gold contra el pipeline y reporta métricas. |
| `/dashboard` | Resumen de observabilidad desde Phoenix. |
| `/redteam` | Ejecuta la checklist de red teaming de seguridad. |
| `/close-session` | Actualiza `SESSION.md`/`CHANGELOG.md` y prepara el cierre de la sesión. |

## Contexto del proyecto

`CLAUDE.md` (en la raíz) define el contexto que el agente lee en cada sesión: stack, estructura, convenciones de idioma y commits, SDD ligero y arquitectura de código (ADR-011).
