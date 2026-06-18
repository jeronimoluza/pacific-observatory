---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 00.5
current_phase_name: cascade-cleanup-behavior-preserving
status: verifying
stopped_at: Completed 00.5-04-PLAN.md
last_updated: "2026-06-18T19:38:23.815Z"
last_activity: 2026-06-18
last_activity_desc: Phase 00.5 execution started
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 9
  completed_plans: 8
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-18)

**Core value:** Every processed price item carries a correct pricing basis, a correct COICOP code, and a correct unit value — verifiable against an independently-labeled gold set — so analysts and dashboards consume price data they can trust.
**Current focus:** Phase 00.5 — cascade-cleanup-behavior-preserving

## Current Position

Phase: 00.5 (cascade-cleanup-behavior-preserving) — EXECUTING
Plan: 6 of 6
Status: Phase complete — ready for verification
Last activity: 2026-06-18 — Phase 00.5 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 00.5 P01 | 22 | 2 tasks | 2 files |
| Phase 00.5 P02 | 20min | 2 tasks | 5 files |
| Phase 00.5 P03 | 4m | 2 tasks | 3 files |
| Phase 00.5 P04 | 13 | 2 tasks | 24 files |
| Phase 00.5 P05 | 12min | 3 tasks | 19 files |
| Phase 00.5 P06 | 8m | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pre-roadmap: Independent gold set must NOT be bootstrapped from `cache/enrichments.parquet` — the existing v2 gold has 190/200 rows accepted from cache predictions unchanged and cannot certify the cache is correct.
- Pre-roadmap: Tier-c fraction must be shrunk to <20% (measured on 5% corpus sample) before full-history reprocessing; widening basket before reducing tier-c will exhaust the 500 RPD Gemini free-tier budget within hours.
- Pre-roadmap: Basket widening deferred until Phase 2 (after tier-a BUG 3/4 fixed); electronics/apparel would flood the cascade with false basis extractions without suppress_window wired.
- Pre-roadmap: COICOP transport (07) deferred — overlaps fuel pipeline.
- Pre-roadmap: Gemini Batch API reserved for Phase 3 full-history reprocessing to work within RPD ceiling.
- [Phase ?]: Phase 0.5 parity anchor SHA is 48b1a750 (one checkpoint ahead of BASELINE.md); eval numbers byte-identical to BASELINE.md
- [Phase ?]: _sub_labels.parquet is a lossy 5-column projection (drops allowed_bases) — cannot be the D-01 source of truth as-is; Plan 02 must widen schema or use xlsx regenerate loader
- [Phase ?]: Plan 00.5-02: COICOP taxonomy migrated to two JSON stores as single source of truth; 30 c{NN}.py/c{NN}_subs.py modules deleted; eval parity identical to PARITY-ANCHOR
- [Phase ?]: 00.5-03: four KNN knobs consolidated into static/enrich_knobs.yaml; config.py loads it at import and re-exports the same constant names (byte-identical, eval-parity proven vs PARITY-ANCHOR.md)
- [Phase ?]: 00.5-03: index.py:514 getattr(config,'MIN_SAME_CHANNEL_KNN',3) left intact — YAML-sourced constant is authoritative so getattr resolves to it; literal fallback unreached, documented not edited (out of plan scope)
- [Phase ?]: Plan 04: PackPattern.kind makes tier-a bucket routing explicit; one MODULE_ORDER replaces the five ID-order tuples; interleaved order resolved by splitting 4 patterns into dedicated modules for byte-identical golden composition
- [Phase ?]: Plan 04: any/->shared/ and _cjk_shared->script/{cjk,latin} via _SCRIPT_OF; pattern lang fields unchanged (load-bearing); load_for dead on live path so reorg is eval-parity-safe
- [Phase ?]: 00.5-05: tier-b consolidated into tier_b/ package; index.py 822->90-line facade; eval parity byte-identical to PARITY-ANCHOR
- [Phase ?]: 00.5-05: reindex_all writes fat per-country meta.json (model_path/git_sha/built_at/knn_score_hard_min) + dir-level manifest.json; ADDITIVE (acceptance reads legacy dim/backend) so base vs fine-tuned indices distinguishable from metadata alone
- [Phase ?]: 00.5-06: bakeoff.py + replay.py removed (gold-unexercised diagnostics, zero live importers, zero orphan imports); eval parity byte-identical to PARITY-ANCHOR

### Pending Todos

None yet.

### Blockers/Concerns

- Eval harness currently in `.claude/worktrees/prices-eval-harness/` — must be merged into `src/prices/enrich/eval/` before Phase 0 can proceed.
- Existing gold at `data/prices/_enrich/gold_labels.parquet` is contaminated (190/200 rows from cache); new independent gold goes to `data/prices/enrich/gold/gold_labels.parquet`.
- Gemini free-tier RPD (500/day) is the central bottleneck for Phase 3; paid-tier API key decision deferred until 5%-sample measurement in Phase 1 is available.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2 | CONF-01: Per-row calibrated confidence score | Planned | Roadmap init |
| v2 | HIER-01: Hierarchical COICOP 4-level columns | Planned | Roadmap init |
| v2 | MODEL-01: Upgrade to multilingual-e5-large-instruct | Planned | Roadmap init |
| v2 | AGG-01: GEKS-Törnqvist aggregation | Planned | Roadmap init |
| Out of scope | COICOP transport (07) | Deferred — overlaps fuel pipeline | Roadmap init |
| Out of scope | Regions beyond EAP | Deferred — later milestone | Roadmap init |

## Session Continuity

Last session: 2026-06-18T19:38:10.722Z
Stopped at: Completed 00.5-04-PLAN.md
Resume file: None
