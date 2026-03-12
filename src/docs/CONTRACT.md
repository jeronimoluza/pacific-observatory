# Source Tree Contract

This file keeps the shared rules for `src/` intentionally small.

## Purpose

- Keep shared guidance grounded in the code that already exists.
- Make `src/docs/` a lightweight reference, not a second planning system.
- Reduce navigation friction without forcing new structures before they are needed.

## Core Rules

- `src/` is for working code, scripts, and operational docs.
- `src/docs/*.md` should stay short, shared, and practical.
- The nearest code, tests, and active outputs are the source of truth.
- Use local READMEs or module-level docs for detailed workflow instructions.
- Do not introduce new top-level package structures until code is actually moving there.

## Documentation Boundaries

- `src/README.md` is the front door for the source tree.
- `src/docs/*.md` holds shared guidance that applies across more than one area.
- Local READMEs and local docs should explain commands, paths, schemas, and caveats for one area.
- If shared docs and local code disagree, fix or remove the docs.

## Change Rules

- Update shared docs only when the shared working approach changes.
- Update local docs when the change is specific to one area.
- Prefer deleting stale plans over preserving them "just in case".
- Keep new documentation tied to runnable commands, real outputs, or repeated maintenance pain.
