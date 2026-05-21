---
description: Cierra la sesión del bloque actual: actualiza SESSION.md y CHANGELOG.md y prepara el commit de cierre
---

Close the current block session following the runbook ritual.

Read the current block from `SESSION.md` (or take it from the argument if provided).

Execute these steps:

1. Read `SESSION.md` and the latest `CHANGELOG.md` entry to recover the current block and what was done this session.

2. **Pre-close verification (local — mirrors CI).** Run all three checks from the `backend/` directory. If any check fails, do NOT proceed to step 3; instead set `Estado` to `blocked` in `SESSION.md`, list the failing checks under `Blockers`, report the output to the user, and stop. Only continue once every check is green.

   a. **Lint:**
      ```bash
      cd backend && uv run ruff check .
      ```
      Expected: `All checks passed!` (exit 0). Any F/E/W code is a blocker.

   b. **Tests:**
      ```bash
      cd backend && uv run pytest tests/ -q
      ```
      Expected: all tests pass (exit 0). Uses mocked Gemini — no network required.

   c. **Commit-message lint** (all commits since the block branch diverged from `main`):
      ```bash
      npx commitlint --from $(git merge-base HEAD main) --to HEAD
      ```
      Expected: exit 0 for every commit in the session. If the branch IS `main` (i.e. commits land directly on main), use the SHA of the previous closing commit as `--from`.

3. Update `SESSION.md`:
   - `Estado`: set to `gate_pending` (or `blocked` if there is an unresolved blocker).
   - `Última actualización`: current timestamp.
   - `Próxima acción concreta`: one sentence with the next step on resume.
   - `Pendientes`: short list of what is left in this block.
   - `Completado en esta sesión`: what got done.
   - `Blockers`: explicit, or "Ninguno".
   - `Decisiones tomadas`: with ADR/spec reference if any.
   - `Gate de revisión`: criterion from the block spec acceptance criteria (`specs/`) and result `pendiente`.

4. Add a `CHANGELOG.md` entry under `## [Bloque X] — YYYY-MM-DD` with `Añadido` / `Cambiado` / `Eliminado` / `Decisiones documentadas` / `Notas`, based on the real diff of this session.

5. Show the user a summary of both updates for review before committing.

6. Propose the closing commit (will ask for confirmation, since git is not auto-allowed):
   - `git add SESSION.md CHANGELOG.md` (plus any pending files the user confirms).
   - `git commit -m "chore(session): close block X"`.
   - `git push` of the block branch.

7. Remind the user that the human gate review comes next: if it passes, open the PR / merge to `main`; if not, document what failed and stay in the block.

Do not mark the block as `completed` here. `completed` is set only after the human gate passes (a human step, not this command). This command leaves the block at `gate_pending`.
