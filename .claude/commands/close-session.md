---
description: Cierra la sesión del bloque actual: actualiza SESSION.md y CHANGELOG.md y prepara el commit de cierre
---

Close the current block session following the runbook ritual.

Read the current block from `SESSION.md` (or take it from the argument if provided).

Execute these steps:

1. Read `SESSION.md` and the latest `CHANGELOG.md` entry to recover the current block and what was done this session.
2. Update `SESSION.md`:
   - `Estado`: set to `gate_pending` (or `blocked` if there is an unresolved blocker).
   - `Última actualización`: current timestamp.
   - `Próxima acción concreta`: one sentence with the next step on resume.
   - `Pendientes`: short list of what is left in this block.
   - `Completado en esta sesión`: what got done.
   - `Blockers`: explicit, or "Ninguno".
   - `Decisiones tomadas`: with ADR/spec reference if any.
   - `Gate de revisión`: criterion from PLAN.md and result `pendiente`.
3. Add a `CHANGELOG.md` entry under `## [Bloque X] — YYYY-MM-DD` with `Añadido` / `Cambiado` / `Eliminado` / `Decisiones documentadas` / `Notas`, based on the real diff of this session.
4. Show the user a summary of both updates for review before committing.
5. Propose the closing commit (will ask for confirmation, since git is not auto-allowed):
   - `git add SESSION.md CHANGELOG.md` (plus any pending files the user confirms).
   - `git commit -m "chore(session): close block X"`.
   - `git push` of the block branch.
6. Remind the user that the human gate review comes next: if it passes, open the PR / merge to `main`; if not, document what failed and stay in the block.

Do not mark the block as `completed` here. `completed` is set only after the human gate passes (see runbook). This command leaves the block at `gate_pending`.
