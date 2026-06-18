---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 00.5
current_phase_name: cascade-cleanup-behavior-preserving
status: executing
stopped_at: Phase 0.5 context gathered
last_updated: "2026-06-18T18:12:12.902Z"
last_activity: 2026-06-18
last_activity_desc: Phase 00.5 execution started
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 9
  completed_plans: 3
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-18)

**Core value:** Every processed price item carries a correct pricing basis, a correct COICOP code, and a correct unit value — verifiable against an independently-labeled gold set — so analysts and dashboards consume price data they can trust.
**Current focus:** Phase 00.5 — cascade-cleanup-behavior-preserving

## Current Position

Phase: 00.5 (cascade-cleanup-behavior-preserving) — EXECUTING
Plan: 2 of 6
Status: Ready to execute
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

Last session: 2026-06-18T18:11:49.904Z
Stopped at: Phase 0.5 context gathered
Resume file: .planning/phases/00.5-cascade-cleanup-behavior-preserving/00.5-CONTEXT.md
