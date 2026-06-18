"""Tier-b pool-filter bake-off (Feature B — companion to ADR-0002 Feature A).

Compares three tier-b accept strategies on a wide-source gold set:

    baseline   — current behavior, no filter applied to the picked neighbors
    hard_drop  — picked neighbors whose 3-digit class prefix is outside the
                 source's allowed set are removed before accept logic
    rank_boost — in-set neighbors get a cosine bonus then the list is resorted
                 (out-of-set neighbors survive as fallback)

Gold = union of
    (a) `static/eval_labels_gold.csv` joined to `static/eval_set.csv`
        — hand-labeled, ~100 rows
    (b) cache rows where `match_method ∈ {tier_c_llm, tier_c_llm_escalated}`
        AND `confidence ≥ 0.9` (synthetic gold from confident LLM rulings)

Restricted to (country, channel) combos that are *wide* — at least 2 distinct
3-digit COICOP prefixes in the cache — because the filter is a no-op on narrow
combos. Per-row allowed prefix set = YAML-declared codes (Feature A's
`declared_coicop_codes` column on products_input.parquet) overriding the
(country, channel) cache-derived prefixes (≥ 5% frequency).

Outputs:
    data/prices/_enrich/_bakeoff/results.parquet  — per-row outcomes
    data/prices/_enrich/_bakeoff/report.md        — markdown summary

The harness does NOT make any LLM calls. It re-uses the existing HNSW indices
and the persisted cache.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.tier_b import cache as cache_mod, index as tier_b_index, pool_filter

logger = logging.getLogger(__name__)

BAKEOFF_DIR = config.ENRICH_DIR / "_bakeoff"
GOLD_CONFIDENCE_FLOOR = 0.9
# Any LLM-resolved method is admissible as synthetic gold. Older caches use
# `legacy_llm`; post-migration runs add `tier_c_llm` / `tier_c_llm_escalated`.
LLM_METHODS = ("legacy_llm", "tier_c_llm", "tier_c_llm_escalated")
WIDE_MIN_DISTINCT_PREFIXES = 2
CACHE_DERIVED_THRESHOLD = 0.05
VARIANTS = ("baseline", "hard_drop", "rank_boost")


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def _load_eval_gold() -> pd.DataFrame:
    """Hand-labeled gold: eval_labels_gold.csv joined to eval_set.csv. Returns
    rows with truth coicop_code, sub_label_id, plus product_name, source,
    country for lookup. `channel` is filled from the per-source YAML lookup."""
    labels_path = _static_dir() / "eval_labels_gold.csv"
    set_path = _static_dir() / "eval_set.csv"
    if not labels_path.exists() or not set_path.exists():
        return pd.DataFrame()
    labels = pd.read_csv(labels_path)
    eval_set = pd.read_csv(set_path)
    if "eval_id" not in labels.columns or "eval_id" not in eval_set.columns:
        return pd.DataFrame()
    joined = labels.merge(
        eval_set[
            ["eval_id", "product_name_original", "source", "country"]
            + ([] if "category" not in eval_set.columns else ["category"])
        ],
        on="eval_id",
        how="inner",
    )
    joined = joined[joined["coicop_code"].notna() & joined["country"].notna()].copy()
    joined["gold_source"] = "hand"
    joined["truth_coicop"] = joined["coicop_code"].astype(str)
    joined["truth_sub_label"] = joined.get("sub_label_id")
    joined["product_name"] = joined["product_name_original"].astype(str)
    joined["category"] = (
        joined.get("category", "").astype(str) if "category" in joined.columns else ""
    )
    # input_hash is NOT in eval_set — compute on the fly so we can look up
    # declared codes via products_input.parquet.
    from prices.enrich.versioning import input_hash

    joined["input_hash"] = joined.apply(
        lambda r: input_hash(
            {
                "product_name_original": str(r["product_name"]),
                "category": str(r.get("category") or ""),
                "country": str(r["country"]),
                "currency": str(r.get("currency") or ""),
            }
        ),
        axis=1,
    )
    return joined[
        [
            "input_hash",
            "country",
            "source",
            "product_name",
            "category",
            "truth_coicop",
            "truth_sub_label",
            "gold_source",
        ]
    ]


def _load_cache_gold(cache_df: pd.DataFrame) -> pd.DataFrame:
    """High-confidence LLM-resolved cache rows usable as synthetic gold. Falls
    back to `cache_key` when `input_hash` is absent (legacy schema)."""
    if cache_df.empty or "match_method" not in cache_df.columns:
        return pd.DataFrame()
    df = cache_df.copy()
    if "input_hash" not in df.columns:
        df["input_hash"] = df.get("cache_key", "")
    mask = (
        df["match_method"].isin(LLM_METHODS)
        & df["confidence"].astype(float).ge(GOLD_CONFIDENCE_FLOOR)
        & df["coicop_code"].notna()
        & df["country"].notna()
        & df["product_name_original"].notna()
    )
    df = df[mask].copy()
    if df.empty:
        return df
    df["gold_source"] = "cache"
    df["truth_coicop"] = df["coicop_code"].astype(str)
    df["truth_sub_label"] = df.get("sub_label_id")
    df["product_name"] = df["product_name_original"].astype(str)
    if "category" not in df.columns:
        df["category"] = ""
    df["category"] = df["category"].fillna("").astype(str)
    if "source" not in df.columns:
        df["source"] = ""
    cols = [
        "input_hash",
        "country",
        "source",
        "product_name",
        "category",
        "truth_coicop",
        "truth_sub_label",
        "gold_source",
    ]
    return df[cols]


def _wide_countries(cache_df: pd.DataFrame) -> set[str]:
    """Countries whose cache holds ≥ WIDE_MIN_DISTINCT_PREFIXES distinct
    3-digit prefixes. Channel-level slicing isn't possible on the current
    cache (legacy rows predate the channel column), so we widen to country
    granularity here; the per-row allowed-prefix set still derives from
    (country, channel) when channel data is available downstream."""
    if cache_df.empty:
        return set()
    sub = cache_df[cache_df["coicop_code"].notna()].copy()
    sub["prefix"] = sub["coicop_code"].apply(pool_filter.class_prefix)
    sub = sub[sub["prefix"] != ""]
    grouped = sub.groupby("country")["prefix"].nunique()
    return {c for c, n in grouped.items() if n >= WIDE_MIN_DISTINCT_PREFIXES}


def _source_to_channel() -> dict[tuple[str, str], str]:
    """(country, source) → channel, via YAML lookup. Mirrors the helper in
    stages/prepare.py — replicated here to avoid importing stages module."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if cfg.channel:
            out[(cfg.country, cfg.source)] = cfg.channel
    return out


def _source_to_yaml_codes() -> dict[tuple[str, str], list[str]]:
    """(country, source) → declared YAML coicop_codes (list). Only populated
    for sources that declare. Requires Feature A's `coicop_codes` field on
    PriceSourceConfig."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], list[str]] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        codes = getattr(cfg, "coicop_codes", None) or None
        if codes:
            out[(cfg.country, cfg.source)] = list(codes)
    return out


def _input_hash_to_declared() -> dict[str, list[str]]:
    """input_hash → declared coicop_codes from products_input.parquet (modal
    declaration after groupby in prepare.py). Empty dict if the parquet isn't
    on disk or the column isn't present."""
    p = config.PRODUCTS_INPUT_PARQUET
    if not p.exists():
        return {}
    try:
        df = pd.read_parquet(p, columns=["input_hash", "declared_coicop_codes"])
    except (KeyError, ValueError):
        return {}
    out: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        codes_str = row.get("declared_coicop_codes") or ""
        codes = [c for c in str(codes_str).split("|") if c]
        if codes:
            out[str(row["input_hash"])] = codes
    return out


def _load_cluster_dfs() -> dict[str, pd.DataFrame]:
    """country → clusters parquet (one per HNSW index)."""
    out: dict[str, pd.DataFrame] = {}
    if not config.TIER_B_INDEX_DIR.exists():
        return out
    for cp in config.TIER_B_INDEX_DIR.glob("clusters_*.parquet"):
        country = cp.stem.removeprefix("clusters_")
        try:
            out[country] = pd.read_parquet(cp)
        except Exception:
            continue
    return out


def _channel_derived_codes_cache(
    cluster_dfs: dict[str, pd.DataFrame],
) -> dict[tuple[str, str], list[str]]:
    """Pre-compute (country, channel) → cache-derived 3-digit prefixes at
    ≥ CACHE_DERIVED_THRESHOLD."""
    out: dict[tuple[str, str], list[str]] = {}
    for country, df in cluster_dfs.items():
        if df.empty or "channel" not in df.columns:
            continue
        for channel in df["channel"].dropna().unique():
            codes = pool_filter.compute_channel_derived_codes(
                df,
                country,
                str(channel),
                threshold=CACHE_DERIVED_THRESHOLD,
            )
            if codes:
                out[(country, str(channel))] = codes
    return out


def _resolve_allowed(
    row,
    declared_by_hash: dict[str, list[str]],
    yaml_by_source: dict[tuple[str, str], list[str]],
    cache_derived: dict[tuple[str, str], list[str]],
) -> set[str]:
    """Per-row allowed 3-digit prefix set."""
    yaml_codes = declared_by_hash.get(str(row["input_hash"]))
    if not yaml_codes:
        yaml_codes = yaml_by_source.get((row["country"], row.get("source") or ""))
    derived = cache_derived.get((row["country"], row.get("channel") or "null"), [])
    return pool_filter.resolve_filter_codes(yaml_codes, derived)


def _apply_variant(
    variant: str,
    picked: list[tuple[int, float]],
    cluster_codes: dict[int, str],
    allowed_prefixes: set[str],
) -> list[tuple[int, float]]:
    if variant == "baseline":
        return picked
    if variant == "hard_drop":
        return pool_filter.apply_hard_drop(picked, cluster_codes, allowed_prefixes)
    if variant == "rank_boost":
        return pool_filter.apply_rank_boost(picked, cluster_codes, allowed_prefixes)
    raise ValueError(f"unknown variant: {variant}")


def _one_row(
    row,
    declared_by_hash,
    yaml_by_source,
    cache_derived,
) -> list[dict]:
    """Run all three variants on a single gold row, return one dict per variant."""
    country = row["country"]
    channel = row.get("channel") or "null"
    picked, cross, clusters_df, reason = tier_b_index.pick_neighbors(
        country=country,
        query_text=row["product_name"],
        channel=channel,
        category=row.get("category") or None,
    )
    out: list[dict] = []
    allowed = _resolve_allowed(row, declared_by_hash, yaml_by_source, cache_derived)
    if picked is None or clusters_df is None:
        for variant in VARIANTS:
            out.append(
                {
                    "input_hash": row["input_hash"],
                    "country": country,
                    "channel": channel,
                    "source": row.get("source"),
                    "gold_source": row["gold_source"],
                    "truth_coicop": row["truth_coicop"],
                    "variant": variant,
                    "accepted": False,
                    "escalation_reason": reason,
                    "predicted_code": None,
                    "predicted_sub_label": None,
                    "in_allowed": False,
                    "allowed_size": len(allowed),
                }
            )
        return out
    cluster_codes = {
        lab: str(clusters_df.iloc[lab].get("coicop_code") or "") for lab, _ in picked
    }
    for variant in VARIANTS:
        filtered = _apply_variant(variant, picked, cluster_codes, allowed)
        if not filtered:
            out.append(
                {
                    "input_hash": row["input_hash"],
                    "country": country,
                    "channel": channel,
                    "source": row.get("source"),
                    "gold_source": row["gold_source"],
                    "truth_coicop": row["truth_coicop"],
                    "variant": variant,
                    "accepted": False,
                    "escalation_reason": "miss_after_filter",
                    "predicted_code": None,
                    "predicted_sub_label": None,
                    "in_allowed": False,
                    "allowed_size": len(allowed),
                }
            )
            continue
        hit = tier_b_index.accept_from_picked(filtered, clusters_df, cross)
        predicted = hit.payload.get("coicop_code") if hit.accepted else None
        in_allowed = (
            bool(predicted and pool_filter.class_prefix(str(predicted)) in allowed)
            if allowed
            else None
        )
        out.append(
            {
                "input_hash": row["input_hash"],
                "country": country,
                "channel": channel,
                "source": row.get("source"),
                "gold_source": row["gold_source"],
                "truth_coicop": row["truth_coicop"],
                "variant": variant,
                "accepted": hit.accepted,
                "escalation_reason": hit.escalation_reason,
                "predicted_code": predicted,
                "predicted_sub_label": hit.payload.get("sub_label_id")
                if hit.accepted
                else None,
                "in_allowed": in_allowed,
                "allowed_size": len(allowed),
            }
        )
    return out


def run_bakeoff(
    sample_size: Optional[int] = None,
    seed: int = 42,
) -> dict:
    cache_df = cache_mod.read_cache()
    if cache_df.empty:
        return {"status": "empty_cache"}

    wide = _wide_countries(cache_df)
    if not wide:
        return {"status": "no_wide_countries"}

    src_channel = _source_to_channel()
    yaml_codes = _source_to_yaml_codes()
    declared_by_hash = _input_hash_to_declared()
    cluster_dfs = _load_cluster_dfs()
    cache_derived = _channel_derived_codes_cache(cluster_dfs)

    eval_gold = _load_eval_gold()
    cache_gold = _load_cache_gold(cache_df)
    gold = (
        pd.concat([eval_gold, cache_gold], ignore_index=True)
        if not (eval_gold.empty and cache_gold.empty)
        else pd.DataFrame()
    )
    if gold.empty:
        return {"status": "no_gold_rows"}

    gold = gold[gold["country"].notna() & gold["product_name"].notna()].copy()
    gold["channel"] = gold.apply(
        lambda r: src_channel.get((r["country"], r.get("source") or ""), "null"),
        axis=1,
    )
    gold = gold[gold["country"].isin(wide)].copy()
    # Drop rows with no resolvable source — without source, YAML codes can't be
    # looked up and the filter degenerates to a no-op (cache-derived alone is
    # rarely populated on legacy caches). The hand-labels always have source;
    # cache gold may not until the cache gets source-stamped post-migration.
    gold["source"] = gold["source"].fillna("").astype(str)
    n_before = len(gold)
    gold = gold[gold["source"].str.len() > 0].copy()
    n_dropped_no_source = n_before - len(gold)
    if gold.empty:
        return {"status": "no_wide_gold_rows", "n_wide_countries": len(wide)}

    if sample_size is not None and sample_size < len(gold):
        gold = gold.sample(n=sample_size, random_state=seed)

    rows_out: list[dict] = []
    for _, gold_row in gold.iterrows():
        rows_out.extend(_one_row(gold_row, declared_by_hash, yaml_codes, cache_derived))

    results = pd.DataFrame(rows_out)
    return {
        "status": "ok",
        "n_gold": len(gold),
        "n_dropped_no_source": n_dropped_no_source,
        "n_wide_countries": len(wide),
        "results": results,
    }


def _summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Per-variant metrics."""
    rows = []
    for variant, sub in results.groupby("variant"):
        n = len(sub)
        accepted = sub[sub["accepted"]]
        correct = accepted[accepted["predicted_code"] == accepted["truth_coicop"]]
        rows.append(
            {
                "variant": variant,
                "n": n,
                "coverage_pct": (len(accepted) / n * 100) if n else 0.0,
                "precision_when_accepted_pct": (len(correct) / len(accepted) * 100)
                if len(accepted)
                else 0.0,
                "n_accepted": len(accepted),
                "n_correct": len(correct),
                "out_of_allowed_when_accepted_pct": (
                    ((~accepted["in_allowed"]).sum() / len(accepted) * 100)
                    if len(accepted)
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def render_report(result: dict) -> str:
    lines = [
        "# Tier-b pool-filter bake-off",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- status: {result.get('status')}",
    ]
    if result.get("status") != "ok":
        return "\n".join(lines)
    lines.extend(
        [
            f"- n gold rows: {result['n_gold']}",
            f"- n wide countries: {result['n_wide_countries']}",
            f"- gold confidence floor (cache rows): {GOLD_CONFIDENCE_FLOOR}",
            f"- cache-derived prefix threshold: {CACHE_DERIVED_THRESHOLD}",
            "",
            "## Per-variant summary",
            "",
            "| variant | n | coverage | precision (when accepted) | accepted | correct | out-of-allowed |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    summary = _summarize(result["results"])
    for _, r in summary.iterrows():
        lines.append(
            f"| {r['variant']} | {r['n']} | {r['coverage_pct']:.1f}% | "
            f"{r['precision_when_accepted_pct']:.1f}% | {r['n_accepted']} | "
            f"{r['n_correct']} | {r['out_of_allowed_when_accepted_pct']:.1f}% |"
        )
    return "\n".join(lines)


def write_outputs(
    result: dict, out_dir: Optional[Path] = None
) -> tuple[Path, Optional[Path]]:
    out_dir = out_dir or BAKEOFF_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    report_path.write_text(render_report(result))
    results_path: Optional[Path] = None
    if result.get("status") == "ok":
        results_path = out_dir / "results.parquet"
        result["results"].to_parquet(results_path, index=False)
    return report_path, results_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    res = run_bakeoff()
    report_path, results_path = write_outputs(res)
    print(f"report → {report_path}")
    if results_path:
        print(f"results → {results_path}")
