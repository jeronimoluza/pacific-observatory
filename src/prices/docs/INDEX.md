# Prices — Documentation Index

The single source of truth for the `src/prices/` pipeline. Start here.

## Living docs (always describe *today* — edit in place)

| Doc | What it is |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The whole pipeline: `collect → process → build → publish`, directory map, CLI. |
| [ENRICH.md](ENRICH.md) | Deep-dive on the enrich/classify stage: two independent jobs, ensemble embedder, LR head + tau, vetoes, two-layer trust model, build wiring. |
| [GLOSSARY.md](GLOSSARY.md) | Controlled vocabulary + the authoritative **Retired — do not use** table. Consult when a term is ambiguous. |
| [SKILLS.md](SKILLS.md) | The `.claude/skills/` entries this pipeline uses — current, partial, and the retired cascade-era skills to distrust. |

## Archives

| Path | What it is |
|---|---|
| [sessions/](sessions/INDEX.md) | Dated development-session logs, newest-first. Where the churn lives. |
| [history/](history/INDEX.md) | Frozen archive of durable findings curated from `.planning/` (triage pending). |

## How to maintain these docs

The point of this layout is that the high-level docs stay small and stable while
day-to-day work is recorded elsewhere. Three rules:

1. **Living docs describe the present.** When the pipeline changes, edit
   ARCHITECTURE / ENRICH / GLOSSARY *in place* so they always reflect today's
   code. Do not append changelog entries to them — that is what sessions are for.
   When you retire a concept, move its term into the GLOSSARY Retired table with
   the current replacement, in the same change.
2. **sessions/ is append-only.** One dated file per work session
   (`YYYY-MM-DD-<slug>.md`, UTC), listed newest-first in `sessions/INDEX.md`.
   Record what you did, what you found, and any backlog you're leaving. This
   absorbs narrative history so the living docs never bloat.
3. **history/ is frozen.** Once a doc is archived there it is not edited. It's the
   raw-findings museum, curated from the old `.planning/` tree.

Reconciliation discipline: when a session changes the pipeline, update the
affected living doc *in the same session* and bump the "Last reconciled" line in
GLOSSARY. If code and a living doc ever disagree, code wins and the doc is stale —
fix the doc and note it in a session.

## Scope note

This set documents **only** the prices pipeline. Documentation is per-pipeline:
each `src/<pipeline>/docs/` is self-contained and `CLAUDE.md` is the hub that
points to them (there is no repo-wide `CONTEXT.md`). Project-wide terms (Region,
Subregion, Country slug, Effective language) live in `CLAUDE.md`. Retired
KNN/tier-b/tier-c cascade concepts are catalogued in GLOSSARY → Retired.
