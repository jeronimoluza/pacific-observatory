# Prices Enrich

Turns raw scraped product rows into structured observations with COICOP codes, structural fields (pricing_basis, amount, units), and sub-labels. Lives under `src/prices/enrich/`.

Two enrichers run, and they cross-check each other:

- **Structural enricher** — extracts quantities from the product name.
- **Categorical enricher** — picks a COICOP leaf + sub_label.
- **Cross-check** — they compare answers; disagreement flags the row.

The "tiers" in `stages/enrich.py` (T0/T1/T2/a/b/c) are internal cheap-to-expensive paths inside the two enrichers, not separate concepts.

## Language

**Structural enricher**:
The enricher that decides a row's quantities: `pricing_basis`, `amount_value`, `standard_unit`, `count`, `multiplier`, promo flags. Currently has one internal path — regex (see [[tier-a]]). Never decides COICOP.
_Avoid_: "tier-a" (that's the internal path, not the enricher), "extractor" (ambiguous with COICOP extract logic).

**Categorical enricher**:
The enricher that decides a row's `coicop_code` + `sub_label_id`. Cheap-to-expensive internal paths: cache lookup ([[T0]]/[[T1]]/[[T2]]) → KNN ([[tier-b]]) → LLM ([[tier-c]]). Whether the LLM labels-from-scratch or audits-KNN-consensus is an internal tactic, not a separate concept.
_Avoid_: "labeler" (privileges one tactic over the other), "classifier" (overloaded).

**Cross-check**:
The mechanism by which the two enrichers compare answers and flag rows where their outputs are mutually implausible. Concrete example: structural says `pricing_basis=mass amount=2000g` and categorical says `external hard drive` — one of them is lying (this is the live "1TB-as-1L" failure mode). **Shipped** as a Phase-2 consolidation layer (`cross_check.py`): `consolidate()` returns a routing bucket (`PASS_THROUGH` / `CLEAN` / `NO_STRUCTURAL` / `SILENT_OVERRIDE` / `ESCALATE_MULTI`); on `SILENT_OVERRIDE` (the sub_label permits exactly one basis and structural disagrees) the cascade rewrites `pricing_basis` + `standard_unit` live (`stages/enrich.py:376,549`). Supersedes the parked [[structural prior]] framing — the cross-check is a live decision-time signal, not a telemetry-only distribution.
_Avoid_: "validator", "sanity check" (already overloaded), "outlier filter".

**Tier-a**:
Regex structural extractor. Overlays non-decisive fields (pricing_basis, amount_value, count, multiplier, promo flags) onto whatever subsequent tier resolves. Never decides COICOP.
_Avoid_: "regex tier" (ambiguous with other regex usages)

**Tier-b**:
Per-country HNSW KNN over the cluster-resolved cache. Accepts when same-channel neighbors agree above thresholds.
_Avoid_: "embedding tier", "vector tier"

**Tier-c**:
KNN-aware LLM reranker. Receives tier-b neighbors as a starting consensus to AUDIT, not re-solve from scratch.
_Avoid_: "LLM tier", "Gemini tier" — model-specific names rot

**Declared `coicop_codes`**:
Per-source YAML field listing COICOP codes a source's rows are expected to carry. Authorial commitment, written at onboarding. Drives the tier-b KNN pool filter when populated.
_Avoid_: "source COICOP", "manifest COICOP"

**Cache-derived codes**:
Top-level COICOP prefixes computed from a source's already-classified cache rows at ≥ 5% frequency. Used at tier-b index build when YAML doesn't declare. YAML overrides cache-derived when both exist.
_Avoid_: "implicit codes", "empirical codes"

**Narrow source**:
A source whose declared `coicop_codes` share a single 3-digit prefix (e.g. `["04.1.1"]` or `["04.1.1", "04.1.2"]` — both under `04.1`). Eligible for the source-curated short-circuit.
_Avoid_: "single-code source", "specialized source"

**Wide source**:
A source whose declared (or derived) codes span more than one 3-digit prefix (e.g. a supermarket). Subject to the tier-b KNN pool filter but never short-circuited.
_Avoid_: "general source", "multi-COICOP source"

**Source-curated short-circuit**:
For `scaffolding: spider` rows from a narrow source, set `coicop_code` to the declared prefix and skip tier-b/c entirely. Tier-a regex still runs; `sub_label_id` stays null. `method = "source_curated"`, `state = "resolved"`, `confidence = 1.0`. See ADR-0002.
_Avoid_: "rentals fast path" (sub-case-specific), "narrow bypass"

**KNN pool filter**:
Tier-b mechanism that restricts the candidate neighbor pool to clusters whose `coicop_code[:LCP]` falls in the source's declared or derived set, where `LCP` is the longest common 3-digit prefix used to define the filter set. Two implementation candidates pending bake-off: hard-drop (out-of-set neighbors removed) vs rank-boost (in-set neighbors get a cosine bonus).
_Avoid_: "KNN restriction", "tier-b prior"

**Bake-off**:
Empirical comparison of hard-drop vs rank-boost using `eval_labels_gold.csv` plus high-confidence LLM-resolved cache rows (confidence ≥ 0.9). Run by `src/prices/enrich/bakeoff.py`. Restricted to rows with resolvable source attribution. Initial run (n=62 filter-active) favored rank-boost (+30.7pp coverage, +2.4pp precision vs baseline); production default kept at `"off"` pending tier-c cache accumulation and broader gold. See ADR-0003.
_Avoid_: "evaluation", "test"

**TIER_B_POOL_FILTER**:
Config flag (`src/prices/enrich/config.py`) gating the production pool-filter mode at the tier-b call site. Values `"off" | "hard_drop" | "rank_boost"`; default `"off"`. Flipping is a one-value change, not a code change.
_Avoid_: "feature flag"

**Regex patterns tree**:
The directory `src/prices/enrich/regex_patterns/` housing tier-a structural-extraction patterns as typed Python modules. Primary axis: `lang/{lang}/` (one folder per language); secondary: `country/{slug}/` (thin override patches); `any/` reserved for patterns whose regex contains no language-identifying chars. Supersedes `static/pack_patterns.yaml` + `static/regex_units.yaml`.
_Avoid_: "regex_patterns.py" (the old monolithic-file mental model)

**Patch file**:
A country-specific tier-a regex override file (`regex_patterns/country/{slug}/patch.py`) that modifies its country's resolved language defaults via three explicit operations: `ADDITIONS`, `REMOVALS` (by pattern id), `REPLACEMENTS` (by pattern id). Applied LAST in the loader — always wins overrides.
_Avoid_: "override file" (too vague), "country regex" (ambiguous with full-clone semantics)

**CJK-shared bundle**:
Tier-a regex patterns shared across Japanese and Chinese, living in `regex_patterns/lang/_cjk_shared/`. Imported by both `lang/ja/__init__.py` and `lang/zh/__init__.py`. Escape hatch for patterns whose CJK characters are common to both scripts (e.g. `枚`) but which would be wrong to mark `any/`.
_Avoid_: "global CJK", "any CJK"

**Byte-identity gate**:
The merge-gate test for tier-a regex refactors: load BOTH the old extractor (extract.py + 2 YAMLs) and the new tree on the 2,054 validated_warm rows; assert byte-identical output across every structural field. Zero diffs required for merge. Lives at `tools/compare_extractors.py`.
_Avoid_: "regression test" (other regression suites have looser gates)

**Keywords tree**:
The directory `src/prices/enrich/keywords/coicop/` containing one `c{NN}.py` file per 2-digit COICOP class (01..15). Each holds a typed `COICOPClass` literal with nested groups → subgroups → leaves. Sub_labels live in a **sibling** `c{NN}_subs.py` file as `SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]]` — split out only because c01 alone has 1,110 sub_labels and inlining would bust the 500-line cap. The registry walks the class tree at load time and injects each leaf's sub_labels via `dataclasses.replace`. `_other` is auto-injected per leaf if not already present. Regenerate `_sub_labels.parquet` from the Python tree via `tools/regenerate_sub_labels_parquet.py`. NOTE: `_sub_labels.parquet` **is** read at runtime — `taxonomy_index.py` (tier-c sub-vocab) and `index.py` (tier-b anchors) both load it — so the Python tree (authoritative for `cross_check.py`) and the parquet + `static/coicop_subcategories.json` (authoritative for tier-b/tier-c) are two live representations kept in sync only by regeneration.
_Avoid_: "coicop terms", "keyword files"

**Allowed bases**:
The `frozenset[str] | None` field on `SubLabel`: the `pricing_basis` values that sub_label permits (e.g. `frozenset({"mass"})`, `frozenset({"mass", "item"})`). `None` means permissive — `_other` is always permissive. At lookup time the cross-check walks sub_label → leaf-union → subgroup-union; `_other` is excluded from union (it would always collapse the union to permissive). Bootstrapped for the top 200 cache slugs from empirical `pricing_basis` distribution in `_tier_b_index_ft/clusters_*.parquet` at ≥ 5% frequency; 412 of 2,988 sub_labels currently have non-None allowed_bases.
_Avoid_: "basis whitelist" (whitelist implies single-mode; this is multi-modal), "expected basis".

**Cross_check.parquet**:
The Phase-1 telemetry written next to `match_log.parquet` (via `prices.enrich.cross_check.append`). Columns: `row_id`, `country`, `structural_basis`, `categorical_code`, `categorical_sub_label`, `allowed_bases_at_finest` (pipe-separated), `resolved_level` (`sub_label`/`leaf`/`subgroup`/`permissive`/`unknown_leaf`/`unknown_class`/`no_code`), `flag_reason` (`""` or `"structural_not_in_allowed_bases"`), `consolidation_bucket`, `matched_at`. Phase 1 wrote this as telemetry only; **Phase 2 now routes** — `consolidate()` acts on the bucket and can rewrite basis/unit (see the **Cross-check** entry above). Two writes per cascade: source-curated and resolved.
_Avoid_: "cross_check_log" (consistency with match_log.parquet, not match_log_log).

**Keyword vote channel**:
The deterministic retrieval signal that runs in PARALLEL to tier-b embedding KNN. An inverted index `keyword → [coicop codes]` built from `coicop/*.py` keywords; at inference, query tokens are looked up and the resulting codes vote. Agreement with KNN top-1 → confidence boost; disagreement → escalate to tier-c. NOT used as query-side embedding enrichment.
_Avoid_: "keyword embedding", "query enrichment"

**Asymmetric passage enrichment**:
The bi-encoder convention where CLUSTER REP passages get the canonical COICOP gloss prepended (`"passage: fish/seafood (mass): salmon fillet"`) but QUERY passages do NOT (they remain `"query: {raw_category} | {first_name}"`). The asymmetry exists because at inference we don't know the query's COICOP — that's what we're predicting.
_Avoid_: "query rewriting", "passage enrichment" (too generic)

**Calibration-as-PR-suggestion**:
The workflow for updating tier-b thresholds. `tools/calibrate_knn_thresholds.py` reads gold sets and emits a STDOUT diff suggesting new values for `KNN_SCORE_HARD_MIN[model]` / `KNN_SCORE_SOFT_MIN[model]` / `KNN_GAP_MIN[model]` in `config.py`. The engineer pastes the diff into a PR; the script NEVER auto-writes config. Reproducibility via `git blame`. NOTE: only `KNN_SCORE_HARD_MIN` is defined in `config.py` today — `KNN_SCORE_SOFT_MIN`/`KNN_GAP_MIN` do not exist (the soft path keys off `KNN_TAU_LOW` + `KNN_SOFT_MAJORITY_MIN`).
_Avoid_: "auto-tune", "dynamic threshold"
