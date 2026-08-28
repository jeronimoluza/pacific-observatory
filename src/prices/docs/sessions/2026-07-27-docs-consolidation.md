# 2026-07-27 — Docs consolidation: establish `src/prices/docs/`

## Goal

Create a scalable, maintainable documentation home for the prices pipeline;
consolidate the scattered truth (up-to-date `enrich/CONTEXT.md`, stale root
`CONTEXT.md`, CLAUDE.md prices section, ~180 outdated `.planning/` files) into a
small set of living docs plus dated session logs and a frozen history archive.

## Approved design

**Principle:** a few *living* high-level docs (edit in place), an append-only
*sessions* log for churn, and a *frozen* history archive curated from `.planning/`.
One source of truth per fact; `INDEX.md` ties it together.

Structure:
```
src/prices/docs/
  INDEX.md          entry point + maintenance rules
  ARCHITECTURE.md   whole pipeline map (collect → process → build → publish)
  ENRICH.md         enrich/classify deep-dive (folds enrich/CONTEXT.md)
  GLOSSARY.md       controlled vocab + authoritative "Retired — do not use" table
  history/INDEX.md  frozen archive index (triage of .planning deferred)
  sessions/INDEX.md rolling newest-first session log
  sessions/2026-07-27-docs-consolidation.md
```

Decisions locked with the user:
- **Scope:** whole prices pipeline (not enrich-only).
- **CONTEXT.md:** fold the **enrich** `CONTEXT.md` fully into `ENRICH.md` and delete
  it. For the **root** `CONTEXT.md`, do the *surgical* version (user chose (a)):
  strip only the two stale prices sections (`Prices enrich cascade`, `Improvement
  loop`), keep the project-wide `Languages and regions` glossary. Rationale: the
  root file is a project-level glossary of mixed scope; a wholesale delete would
  also kill the still-current non-prices terms.
- **History:** migrate valuable `.planning` docs into `history/` — but **deferred**
  to a later session (living docs first). `history/INDEX.md` is a stub for now.
- **Sessions:** dated logs + rolling index (this file is entry #1).

## Design revision (later in the same session)

The user refined the docs architecture after the first pass shipped. Locked
changes:

- **No `CONTEXT.md` anywhere.** Documentation is strictly **per-pipeline** under
  `src/<pipeline>/docs/`, and `CLAUDE.md` is the hub that points to each. The
  earlier "surgical root `CONTEXT.md`" decision (keep `Languages and regions`) is
  **superseded**: the root `CONTEXT.md` (untracked, local-only) was deleted and
  its content moved into `CLAUDE.md` — Region/Subregion/Country slug were already
  in the Configuration section; the **Effective language** gotcha was added there.
- **`SKILLS.md` per pipeline.** Each documented pipeline lists the `.claude/skills/`
  it uses in `src/<pipeline>/docs/SKILLS.md`. Created `src/prices/docs/SKILLS.md`:
  current (`onboard-country-price-sources`, `iterate-retailer-unit-values`),
  partial (`spike-findings-template-repo` — tier-a current / tier-b dead), and
  **four** retired cascade skills. This upgrades the F2 count from three to four —
  `resolve-price-conflicts` (W5 consensus/witness, `prices classify-corpus`,
  gazetteer flywheel) is also cascade-era and stale.
- **`CLAUDE.md` wiring.** Added a canonical-docs pointer + per-pipeline convention
  note to the Prices section, the Effective-language term to Configuration, and a
  delegation-to-`SKILLS.md` note (naming the four stale skills) to Project skills.

Follow-on wiring changes: `INDEX.md` now lists `SKILLS.md` and its scope note
points to `CLAUDE.md` (not `CONTEXT.md`); `GLOSSARY.md` scope note likewise.
`match_record.py:6`'s `CONTEXT.md` reference is now fully phantom (was already
broken — still F6 backlog). Future: `src/text/docs/` + its `SKILLS.md` when text
gets the same treatment.

## What shipped this session

- New living docs: `INDEX.md`, `ARCHITECTURE.md`, `ENRICH.md`, `GLOSSARY.md`.
- Scaffolding: `sessions/INDEX.md`, `history/INDEX.md` (stub), this session note.
- Root `CONTEXT.md`: stale prices sections stripped, project-wide terms kept.
- `enrich/CONTEXT.md`: content folded into `ENRICH.md`, file removed.

## Findings — `/disambiguate` audit (scoped to `src/prices/`)

Headline: the KNN/HNSW tier-b/tier-c cascade was **genuinely removed from the
runtime** (2026-07-24). No live code path reads `enrichments.parquet`; no
`KNN`/`HNSW`/`cluster_key` symbol survives in Python; `classify` runs only
`extract()` + `(embedding→head)` + vetoes. The residue is in docs, comments,
prompts, orphan artifacts, and — most dangerously — **three skill descriptions**.

Findings (F#, severity):
- **F1 (high)** — root `CONTEXT.md` narrates the retired cascade as the live
  glossary. *Resolved this session:* stripped.
- **F2 (high, loud)** — `base_item` / `prices classify` GREEN workflow exists
  **only in skill prose**, not in code: `base_item` appears 0× in `src/`, and
  `cli.py` registers no `classify` verb. Skills `classify-base-item-prices`,
  `diagnose-prices-cascade`, `improve-prices-cascade` describe `base_items.parquet`
  / `gazetteer.parquet` / `validation_runs/` / CANDIDATE→GREEN / live tier-a-b-c as
  current. **Top agent-drift surface** (skills auto-surface as capabilities).
- **F3 (high)** — `enrich/boilerplate.py` is dead code; its docstring cites tier-b
  and contradicts CONTEXT (RAW name is fed to the embedder).
- **F4 (med)** — `enrich/prompts/enrich_system.md:32` still emits `sub_label_id`;
  the file is byte-hashed live by `versioning.py:23` (`PROMPT_BYTES_HASH`).
- **F5 (med)** — `enrich/CONTEXT.md:7` wrongly retires "consensus", which is a
  **live** gold-labeling term (`label_cli.py`, `label_merge.py`). GLOSSARY scopes
  this: cascade-consensus retired, gold two-labeler consensus current. (`witness`
  is genuinely dead.)
- **F6 (med)** — phantom doc anchors: `match_record.py:6` cites a CONTEXT.md
  section "Recorder data path" that exists nowhere; `§9`/`§5.2`/`§2` anchors in
  `census.py`, `shape_label.py`, `audit_monitor.py`, `compare_extractors.py`,
  `import_coicop_xlsx.py` point to specs not present under `src/prices/`.
- **F7 (med/low)** — stale tier-b/c comments in **live** configs:
  `configs/_examples/template.yaml:19,38` (the clone template!), `momo_tw.yaml:13`,
  `laostatefuel.yaml:20`, and source comment `normalize.py:286`.
- **F8 (med)** — retired sub_label artifacts still on disk and rebuilt by tools:
  `keywords/coicop/_sub_labels_store.json`, `_sub_labels.parquet`, `_class_tree.json`,
  `_retrieval_legacy.parquet`; `tools/rebuild_sub_labels_store.py`,
  `import_coicop_xlsx.py build_sub_labels_df`.
- **F9 (low)** — orphan `enrich/static/eval_labels_gold.csv` carries a
  `sub_label_id` column, no consumer.
- **F10 (low)** — `enrich/rate_limit.py:1` docstring says "tier-c" for what are now
  gold-labeling Gemini calls (module is live, wording is stale).

All retired terms and their current replacements are catalogued in
`GLOSSARY.md → Retired — do not use`.

## Backlog (NOT done this session — "living docs first")

Deliberately deferred; each is a scoped follow-up:
1. **`.planning/` → `history/` triage** (KEEP/SUPERSEDED/DROP; user-gated KEEP list).
2. **Retire or rewrite the 3 cascade-era skills** (F2) — highest drift risk.
3. Flag/delete `boilerplate.py` (F3).
4. Drop `sub_label_id` from `enrich_system.md`, verify no gold-labeling script needs
   it (F4).
5. Fix/inline the phantom `§`/"Recorder data path" doc anchors (F6).
6. Strip tier-b/c rationale from `template.yaml` + the two source YAMLs + the
   `normalize.py:286` comment (F7).
7. Decide fate of sub_label artifacts + `rebuild_sub_labels_store.py`; remove
   orphan `eval_labels_gold.csv` (F8, F9).
8. Reword `rate_limit.py` "tier-c" → "gold-labeling LLM" (F10).
9. Confirm whether `channel`/`aggregator`/`hypermarket` still has a live consumer
   post-cascade, or document as inert-but-propagated.

## Notes / gotchas

- `template-repo` is **876 commits ahead of `origin/main`**, and `src/prices/` does
  not exist on `main`. A default worktree (branches fresh from `origin/main`) would
  yield a codebase with no prices pipeline — so this work was done **in place**, per
  the repo's "worktrees off" convention. Root `CONTEXT.md` is untracked (local-only).
- `match_record.py:6`'s phantom CONTEXT.md reference was left untouched (surgical:
  it was already broken before this session; fixing it is F6 backlog).
