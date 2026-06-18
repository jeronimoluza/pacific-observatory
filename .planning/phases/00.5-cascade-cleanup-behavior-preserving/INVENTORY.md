# Phase 0.5 INVENTORY — read-only blast-radius map (SC1)

**Captured:** 2026-06-18 (UTC) · **Tree:** `48b1a750` (same as PARITY-ANCHOR.md)

> **READ-ONLY ASSERTION:** No file under `src/` was edited to produce this inventory.
> Every finding below is from `grep`/`wc`/`coverage` over the existing tree.
> `git diff --quiet -- src/prices` passes at write time (verified). The only files
> this plan creates are `PARITY-ANCHOR.md` and this `INVENTORY.md`, both under
> `.planning/`.

This is the gate for plans 02–06. Nothing is deleted, moved, or reshaped here.

---

## (1) DEAD-PATH CANDIDATES

### 1a. Whole units — zero live importers (APPROVE-ONCE per D-06)

| Unit | Lines | Importer grep (in `src/prices`, excluding own file) | Coverage on 313-gold eval | Gold tag | Disposition |
|---|---|---|---|---|---|
| `enrich/bakeoff.py` | 522 | **NONE** — `grep -rn "bakeoff" src --include="*.py"` returns only its own file | **0%** (`30-522` never executed) | gold-UNexercised | **APPROVE-ONCE** (manual diagnostic) → feeds Plan 06 |
| `enrich/replay.py` | 334 | **NONE** — the only `replay` hits in `src` are unrelated docstring words (Wayback "replay", snapshot "replay" in spiders/`tier_c.py:107`), not module imports | **0%** (`17-334` never executed) | gold-UNexercised | **APPROVE-ONCE** (manual diagnostic) → feeds Plan 06 |

Grep evidence (verbatim):
- `grep -rn "bakeoff" src --include="*.py" | grep -vE "enrich/bakeoff\.py"` → **NONE**
- `grep -rn "replay" src --include="*.py" | grep -vE "enrich/replay\.py"` → only
  `fuel/.../csph.py:291` (Wayback cap comment), two spider docstrings, and
  `enrich/stages/tier_c.py:107` ("smoke replay" comment) — **no import of `replay`**.
- Neither module is referenced in `run.py` or `src/cli.py`.

Both are the textbook D-06 case: unimported, possibly hand-run diagnostics, gold
almost certainly never exercises them → surfaced for the single approve-once pass
rather than silent auto-delete.

**Confirmed LIVE (do NOT remove)** — caller evidence:
- `cross_check.py` ← `stages/enrich.py` (and imports `_registry`, see §3).
- `embed.py` ← `index.py`, `stages/tier_c.py`.
- `rate_limit.py` ← `stages/tier_c.py`.
- `taxonomy_index.py` ← `stages/tier_c.py`.
- `index.py` (tier-b) ← `stages/enrich.py`, `enrich/cli.py`.

### 1b. Intra-module dead branches (D-07) — from a STATIC tool, not eyeballing

`vulture` is **NOT installed** (`vulture --version` → command not found), so per the
plan's Task-2 fallback the static signal is **coverage of the 313-row gold eval**:

```bash
poetry run coverage run --source=src/prices/enrich run.py prices eval --no-write
poetry run coverage report --show-missing
```

The eval scorecard reproduced the parity numbers under instrumentation (coicop
73/313), so the coverage map reflects the real cascade path. Per-module
never-executed lines on the deterministic (tier-c OFF) baseline:

| File | Stmts | Missed | % | Never-run line ranges (D-07 candidates) | Read carefully |
|---|---|---|---|---|---|
| `bakeoff.py` | 227 | 227 | 0% | `30-522` | whole module (see 1a) |
| `replay.py` | 152 | 152 | 0% | `17-334` | whole module (see 1a) |
| `stages/tier_c.py` | 314 | 269 | 14% | `58-67,71-84,111-148,159-186,…,688-769` | **NOT dead** — tier-c is OFF in this baseline; these are the LLM path, gold-unexercised BY DESIGN |
| `taxonomy_index.py` | 97 | 81 | 16% | `27-42,56-90,99-104,115,132-174,180-186` | tier-c-side helper (built for the LLM prompt) — gold-unexercised, not dead |
| `rate_limit.py` | 131 | 101 | 23% | `43-50,…,196-211` | only fires on real LLM calls — tier-c OFF ⇒ unexercised, not dead |
| `embed.py` | 146 | 91 | 38% | `69-82,91-110,114-118,128-170,175-185,200,207-218` | mostly the e5/gemini embed + index-build path; build path not hit by eval |
| `regex_patterns/_registry.py` | 99 | 57 | 42% | `35-37,48-49,52,59,67,72-75,85-86,98-102,108-116,143-176,182-184` | loader fallbacks; needs caller-evidence pass in Plan 06 |
| `index.py` | 353 | 181 | 49% | `51,61,80,99-100,132-153,158-164,171-255,267,279-432,…,815-822` | mixes genuine guards (`51`,`61` parquet-missing) + **build-path** (`reindex_all` 778+, called from `cli.py:100`, not eval) |
| `stages/enrich.py` | 267 | 89 | 67% | `61-62,120-123,157-195,206-220,250,319-326,332-333,342-423,447,490,530,546-549,554,563,612-638` | orchestration branches for non-baseline configs (brand-prior, channel fallback) |
| `extract.py` (tier-a) | 208 | 63 | 70% | `146-151,157,172,174,193-208,226,229-250,260,283,327,338,369-374,417-420,428-438` | regex branches no gold row triggers |
| `normalize.py` | 165 | 32 | 81% | `88,102,127-130,164,176,260-269,281-294` | CJK/edge normalize branches |
| `_registry.py` | 73 | 7 | 90% | `28-29,57,71,118-119,122` | **defensive guards** — `ModuleNotFoundError` fallbacks + `raise RuntimeError` validation; NOT dead |
| **TOTAL** | 3710 | 1922 | **48%** | | |

**Caller-evidence spot-checks (representative, to show the tagging discipline Plan 06 must apply per candidate):**
- `_registry.py:28-29` = `except ModuleNotFoundError: return {}` — a defensive
  fallback for a missing `c{NN}_subs` module. Live guard, **not** dead.
- `_registry.py:57,71` = `raise RuntimeError(...)` orphan/dangling-exclude
  validators — fire only on a malformed taxonomy. Live guard, **not** dead.
- `index.py:51,61` = `if not p.exists(): return pd.DataFrame()/{}` — missing-parquet
  guards. Live guard, **not** dead.
- `index.py:792 reindex_all` (range `778-822`) = called from `enrich/cli.py:100`
  (the index-build subcommand), **not** from the eval path → gold-unexercised but
  **LIVE on the build path**, **not** dead.

> **D-08 / coverage-blindness statement (REQUIRED):** Aggregate eval parity (D-08)
> is **blind to any line the 313-row gold does not run**. Coverage-from-eval flags
> *unexercised* lines, but unexercised ≠ dead: the table above is dominated by
> (i) the tier-c LLM path (OFF in the deterministic baseline), (ii) the index-BUILD
> path (run by `cli.py`, not by eval), and (iii) defensive guards. **None of these
> may be auto-deleted on coverage alone.** Every intra-branch D-07 candidate is
> therefore routed to **Plan 06's approve-once `DEAD-CODE-APPROVE.md`** with its
> file:line + a caller-evidence verdict (`dead` vs `live-but-unexercised`).
> **Un-inventoried branches are OUT of scope for this phase.** The static-discovery
> list here + the Plan 06 approve-once pass are the required compensation for the
> path-coverage half of the D-08 gap.

---

## (2) KNOB MAP (grounds D-04)

All four KNN knobs + the channel-priors path are **single-defined in
`src/prices/enrich/config.py`** and consumed via `config.<NAME>` at every site —
**no inline redefinition** anywhere in `src/prices`.

| Knob | config.py def | Literal value | Import/use sites (all via `config.<NAME>`) |
|---|---|---|---|
| `KNN_BOOTSTRAP_CLUSTER_FLOOR` | L86 | `150` | `index.py:393,487`; doc refs `index.py:391`, `cli.py:59` |
| `KNN_CLUSTER_AGREEMENT_MIN` | L77 | `0.90` | `index.py:637,656`; `stages/enrich.py:80`; `eval/runner.py:94`; doc refs `cli.py:74`, `stages/enrich.py:76` |
| `KNN_SUB_LABEL_AGREEMENT_MIN` | L84 | `0.90` | `index.py:629`; doc refs `index.py:576`, `stages/tier_c.py:652` |
| `MIN_SAME_CHANNEL_KNN` | L114 | `3` | `index.py:514` via `getattr(config,"MIN_SAME_CHANNEL_KNN",3)` ⚠; doc refs `index.py:766`, `cli.py:73` |
| `CHANNEL_COICOP_PRIORS_PATH` | L129 | `static/channel_coicop_priors.yaml` | `stages/tier_c.py:60` |
| (bonus) `TIER_B_INDEX_DIR` | L116 | `$TIER_B_INDEX_DIR` or `_enrich/_tier_b_index` | `index.py:259,263,267,419`; `bakeoff.py:228,230`; `stages/enrich.py:115,116` |

⚠ **Note for D-04:** `MIN_SAME_CHANNEL_KNN` is read once via
`getattr(config, "MIN_SAME_CHANNEL_KNN", 3)` (a `getattr` with a literal `3`
fallback), not bare `config.MIN_SAME_CHANNEL_KNN`. The fallback `3` equals the
config value, so behavior is identical today — but when D-04 moves the knob to YAML,
this `getattr` default must be kept in sync (or removed) so the YAML value is
authoritative. Flagged so Plan 03 doesn't leave a stale literal behind.

All other tuning knobs (the deprecated `KNN_TAU_HIGH/LOW` scalars, high-cos override
trio, brand-prior band, rate limits, pool filter) are likewise centralized in
`config.py`. **No knob is defined twice or hardcoded at a call site** — D-04's
consolidation is a pure relocation, values byte-identical (D-05).

---

## (3) TAXONOMY DATA-FLOW — BOTH families (grounds D-01/D-02)

### 3a. Both families are PURE auto-generated DATA (no logic)

Static check (`grep -nE "^\s*(def|if|for|while|class|with|try:|lambda)"`):

| Family | Files | Logic lines | Top-level names |
|---|---|---|---|
| `c{NN}_subs.py` (SUB_LABELS_BY_LEAF) | c01–c15 (15 files) | **0** in every file | 1 (`SUB_LABELS_BY_LEAF`) |
| `c{NN}.py` (CLASS tree) | c01, c05, c09 spot-checked | **0** | exactly **1** (`CLASS`) |

Both confirmed pure data: header says "auto-generated by `tools/import_coicop_xlsx.py`"
(for `c{NN}.py`) / "Auto-generated … Regenerate via …generate_subs_sidecars.py"
(for `c{NN}_subs.py`). No hand-edited logic crept in.

### 3b. LIVE importers (producer/consumer facts D-01/D-02 needs)

Two **distinct** runtime consumers — they read DIFFERENT artifacts:

| Consumer | Reads | Of which family | Evidence |
|---|---|---|---|
| `keywords/_registry.py` | the **`c{NN}_subs.py` Python modules** via `importlib.import_module(f"…c{NN}_subs")` → `SUB_LABELS_BY_LEAF`; and `c{NN}.py` → `CLASS` | BOTH families, in-process | `_registry.py:24-30` (subs), `:115-125` (CLASS+inject) |
| `cross_check.py` | calls `registry.load(cc)` | BOTH (via `_registry`) | `cross_check.py:25,58` (← `stages/enrich.py`) |
| `index.py` (`_load_anchors`) | the **`_sub_labels.parquet` sidecar** (NOT the .py) | derived parquet | `index.py:49-55` |
| `taxonomy_index.py` | the **`_sub_labels.parquet` sidecar** | derived parquet | `taxonomy_index.py:144,155` |

> **DIRECTION (the central D-01 fact — a stale docstring contradicts the truth):**
> The `c{NN}_subs.py` header says *"Source: `_sub_labels.parquet`"* (suggesting
> parquet→py), but the actual current generators say the **opposite**:
> - `tools/import_coicop_xlsx.py` (the generator): writes `c{NN}.py` + `c{NN}_subs.py`
>   FROM `coicop_categories.xlsx`, and explicitly states `_sub_labels.parquet` is
>   *"no longer written here"* (`:490,531`).
> - `tools/regenerate_sub_labels_parquet.py` (the derivation): exports
>   `c{NN}_subs.py SUB_LABELS_BY_LEAF → _sub_labels.parquet`, docstring:
>   *"c{NN}_subs.py … are the hand-curated source of truth … parquet … is a derived
>   artifact"* and CLI desc *"source of truth: Python"*.
>
> **Resolved current truth:** `coicop_categories.xlsx` (under `data/`, READ-ONLY)
> → `import_coicop_xlsx.py` → `c{NN}.py` (CLASS) + `c{NN}_subs.py` (SUB_LABELS) →
> `regenerate_sub_labels_parquet.py` → `_sub_labels.parquet` (lossy projection,
> see 3c). The `.py` modules are today's source of truth; the parquet is derived.
> The "Source: _sub_labels.parquet" line in the `c{NN}_subs.py` headers is **stale
> and misleading** — Plan 02 must not treat it as authoritative.

No OTHER live importer of either family exists in `src/prices` beyond the four rows
above (grep of `SUB_LABELS_BY_LEAF`, `coicop.c[0-9]`, `registry.load`, `.CLASS`).

### 3c. STORE FIELD/COLUMN COVERAGE (can the store reconstruct both? — gate for D-01)

**SubLabel record** (`keywords/types.py:15-23`):
`id, label, keywords_by_lang{lang:tuple}, allowed_bases (frozenset|None), role, numeric_id`.

**`_sub_labels.parquet` emitted columns** (from `regenerate_sub_labels_parquet.py:79-89`):
`coicop_code, id, label, lang, role` — **5 columns only**, one row per (keyword, lang).

> ⚠ **DECISIVE FINDING for D-01:** `_sub_labels.parquet` is a **LOSSY** projection.
> `regenerate_sub_labels_parquet.py` **drops `allowed_bases`** entirely and explodes
> `keywords_by_lang` into one row per keyword (losing the tuple grouping; `numeric_id`
> is folded into `coicop_code` and not preserved as a separate field). **The parquet
> as it exists today CANNOT reconstruct the full SubLabel record** (no `allowed_bases`,
> no clean `numeric_id`). Therefore the parquet **cannot become the single source of
> truth as-is** — D-01 either (a) widens the parquet schema to carry all SubLabel
> fields, or (b) keeps a richer store. This is the content-preservation gate the
> inventory exists to surface.

**COICOPClass tree** (`keywords/types.py:25-53`): HIERARCHICAL —
`COICOPClass(code,label,groups[Group(code,label,subgroups[Subgroup(code,label,
leaves[Leaf(code,label,keywords_by_lang,excludes[ExcludeRef(code,label,lang)],
sub_labels)])])])`. A flat parquet **cannot** carry this nesting without a tree
encoding; sub-labels are FLAT, the class tree is HIERARCHICAL.

**Recommended store shape (simplest + content-preserving):** keep **two artifacts** —
(1) a class-tree store under `src/` (the hierarchical CLASS data; JSON/parquet-of-rows
with a path encoding, or a regenerate-from-xlsx loader) and (2) the flat sub-label
store — but **fix the sub-label store to carry ALL SubLabel fields**
(`allowed_bases`, full `keywords_by_lang`, `numeric_id`) before it can be truth.
Given the lossy-projection finding, the **lowest-risk content-preserving path** is a
**regenerate-from-xlsx loader** (xlsx is already the upstream truth via
`import_coicop_xlsx.py`) OR a schema-widened sub-label store — Plan 02 picks, but it
**must not** adopt the current 5-column parquet as truth.

Tooling (note for Plan 02; xlsx source is under `data/` ⇒ **READ-ONLY** for executor):
- generator: `src/prices/tools/import_coicop_xlsx.py` (xlsx → `c{NN}.py` + `c{NN}_subs.py`)
- derivation: `src/prices/tools/regenerate_sub_labels_parquet.py` (`c{NN}_subs.py` → parquet)

---

## (4) FILE-SPLIT CANDIDATES (every `enrich/` .py > 500 lines)

`find src/prices/enrich -name "*.py" | wc -l`, filtered to > 500:

| File | Lines | Disposition |
|---|---|---|
| `keywords/coicop/c01_subs.py` | 10054 | **dissolve via Plan 02** (D-01/D-02 — data leaves .py) |
| `keywords/coicop/c09_subs.py` | 2860 | dissolve via Plan 02 |
| `keywords/coicop/c07_subs.py` | 2521 | dissolve via Plan 02 |
| `keywords/coicop/c05_subs.py` | 2361 | dissolve via Plan 02 |
| `keywords/coicop/c03_subs.py` | 2156 | dissolve via Plan 02 |
| `keywords/coicop/c04_subs.py` | 2150 | dissolve via Plan 02 |
| `keywords/coicop/c06_subs.py` | 1848 | dissolve via Plan 02 |
| `keywords/coicop/c15_subs.py` | 1507 | dissolve via Plan 02 |
| `keywords/coicop/c13_subs.py` | 1403 | dissolve via Plan 02 |
| `keywords/coicop/c08_subs.py` | 1144 | dissolve via Plan 02 |
| `keywords/coicop/c02_subs.py` | 1118 | dissolve via Plan 02 |
| `index.py` | 822 | tier-b package move (**Plan 05**) |
| `keywords/coicop/c01.py` | 739 | **dissolve via Plan 02** (CLASS-tree migration) |
| `keywords/coicop/c09.py` | 569 | dissolve via Plan 02 (CLASS-tree migration) |
| `keywords/coicop/c05.py` | 550 | dissolve via Plan 02 (CLASS-tree migration) |
| `bakeoff.py` | 522 | **Plan 06** dead-code removal (APPROVE-ONCE, §1a) |
| `stages/tier_c.py` | 769 | **DEFERRED to Phase 1** — acknowledged over-500 exception |
| `stages/enrich.py` | 638 | **DEFERRED to Phase 1** — acknowledged over-500 exception |

> **DEFERRED (over-500 exceptions for THIS phase):** `stages/tier_c.py` (769) and
> `stages/enrich.py` (638) are orchestration CODE (not migratable data) and are the
> exact files Phase 1 rewrites when hardening the cascade. Splitting them now then
> rewriting in Phase 1 is double-churn, so the SC3 line-limit gate at execution is
> scoped to phase-touched files and treats these two as acknowledged over-500
> exceptions (per 00.5-CONTEXT.md `<deferred>`).

Once Plan 02 dissolves the `c{NN}_subs.py` + `c{NN}.py` sprawl (16 files, ~33k lines)
and Plan 05 packages `index.py`, the only remaining > 500 `enrich/` files are the two
deferred `stages/` orchestrators — exactly as scoped.

---

## APPROVE-ONCE list (the D-06 gold-unexercised set → Plan 06)

1. `enrich/bakeoff.py` (whole module, 0% coverage, zero importers).
2. `enrich/replay.py` (whole module, 0% coverage, zero importers).
3. The §1b intra-module never-run branches — each routed to Plan 06's
   `DEAD-CODE-APPROVE.md` with its file:line + a `dead` vs `live-but-unexercised`
   verdict (most are tier-c-path / build-path / defensive guards = live, NOT dead).

---

## Read-only proof

`git diff --quiet -- src/prices` → **clean** (zero source edits). The coverage run
produced a repo-root `.coverage` data file which was removed after the report; no
`src/` file was touched.
