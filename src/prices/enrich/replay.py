"""Cascade replay verification (Phase 4.5).

Leave-one-out replay over the existing enrichments cache. For each test
row, the row is hidden from the lookup index and the cascade is run
against the remaining cache. The predicted enrichment payload is
compared against the held-out row's payload, bucketed by which tier fired.

Why leave-one-out and not random train/test split: post-Phase 1 the cache
is deduplicated by input_hash, so random splits give Tier 0 zero hits by
construction and Tier 1/2 fire only on the few pids that have multiple
cache rows. Leave-one-out targets exactly those collision sets.

The LLM tier is hard-disabled — any residual product is reported but not
enriched.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.config import load_countries
from prices.enrich.normalize import canonicalize
from prices.enrich.tier_b import cache
from prices.enrich.stages.enrich import _PAYLOAD_FIELDS  # noqa: F401  (re-exported for backwards compat)

REQUIRED_COLUMNS = [
    "input_hash",
    "product_name_original",
    "country",
    "currency",
    "coicop_code",
]

# Semantic agreement = classification only. Numeric / derived fields
# (amount_value, count, multiplier, dimensions_json, confidence) legitimately
# vary across observations of the same identity — they reflect how the
# specific observation phrased the product, not the COICOP classification.
SEMANTIC_FIELDS = [
    "coicop_code",
    "sub_label_id",
    "pricing_basis",
    "standard_unit",
    "state",
]


def _country_lang_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


def _derive_identity(row, lang_map: dict[str, str]) -> tuple[str, str]:
    country = str(row.get("country") or "")
    canon = canonicalize(
        item_name=str(row.get("product_name_original") or ""),
        category=(str(row.get("category") or "") or None),
        country=country,
        lang=lang_map.get(country) or None,
    )
    pid = canon.canonical_strict or f"__empty__:{row.get('input_hash', '')}"
    return pid, canon.canonical_loose


def _filter_replayable(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            return df.iloc[0:0]
    mask = df[REQUIRED_COLUMNS].notna().all(axis=1)
    return df[mask].copy()


def _payload_eq(
    predicted: dict, truth: dict, fields: Optional[list[str]] = None
) -> bool:
    """Compare two enrichment payloads. Defaults to semantic-only (classification
    fields). Pass `fields=_PAYLOAD_FIELDS` for strict whole-payload equality."""
    if fields is None:
        fields = SEMANTIC_FIELDS
    for f in fields:
        a = predicted.get(f)
        b = truth.get(f)
        if pd.isna(a) and pd.isna(b):
            continue
        if a != b:
            return False
    return True


def _prepare(cached: pd.DataFrame) -> pd.DataFrame:
    df = _filter_replayable(cached)
    if df.empty:
        return df
    lang_map = _country_lang_map()
    identities = df.apply(
        lambda r: pd.Series(
            _derive_identity(r, lang_map),
            index=["product_identity_key", "canonical_loose"],
        ),
        axis=1,
    )
    for col in ("product_identity_key", "canonical_loose"):
        if col in df.columns:
            df = df.drop(columns=[col])
    return pd.concat(
        [df.reset_index(drop=True), identities.reset_index(drop=True)], axis=1
    )


def _build_indexes(
    df: pd.DataFrame,
) -> tuple[
    dict[str, list[int]], dict[str, list[int]], dict[tuple[str, str], list[int]]
]:
    """Build lookup indexes that return ALL row positions for each key, so the
    caller can exclude `self` during leave-one-out."""
    hash_idx: dict[str, list[int]] = defaultdict(list)
    pid_idx: dict[str, list[int]] = defaultdict(list)
    loose_idx: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, row in df.iterrows():
        h = row.get("input_hash")
        pid = row.get("product_identity_key")
        loose = row.get("canonical_loose")
        country = row.get("country")
        if isinstance(h, str) and h:
            hash_idx[h].append(i)
        if isinstance(pid, str) and pid:
            pid_idx[pid].append(i)
        if isinstance(loose, str) and loose and isinstance(country, str) and country:
            loose_idx[(loose, country)].append(i)
    return hash_idx, pid_idx, loose_idx


def _collision_set(
    df: pd.DataFrame,
    pid_idx: dict[str, list[int]],
    loose_idx: dict[tuple[str, str], list[int]],
) -> pd.Index:
    """Indices of rows that have at least one buddy (same pid OR same loose+country)."""
    keep: set[int] = set()
    for positions in pid_idx.values():
        if len(positions) >= 2:
            keep.update(positions)
    for positions in loose_idx.values():
        if len(positions) >= 2:
            keep.update(positions)
    return pd.Index(sorted(keep))


def replay(
    seed: int = 42,
    sample_size: Optional[int] = None,
    cached: Optional[pd.DataFrame] = None,
    scope: str = "collisions",
) -> dict[str, Any]:
    """Run a leave-one-out cascade replay.

    Args:
        seed: deterministic sampling seed.
        sample_size: cap on test rows (after scope filter). None = all.
        cached: pre-loaded cache; when None, reads from disk.
        scope: 'collisions' (default) restricts the test set to rows with
               at least one pid- or loose+country-buddy. 'all' tests every row.

    Returns:
        Dict with status, n_pool/n_test, residual count, per-tier buckets,
        disagreement list, and cache-shape stats.
    """
    if cached is None:
        cached = cache.read_cache()
    if cached.empty:
        return {"status": "no_cache", "rows": 0}

    df = _prepare(cached)
    if df.empty:
        return {"status": "no_replayable_rows", "rows": 0}

    hash_idx, pid_idx, loose_idx = _build_indexes(df)
    n_pid_collisions = sum(1 for v in pid_idx.values() if len(v) >= 2)
    n_loose_collisions = sum(1 for v in loose_idx.values() if len(v) >= 2)

    if scope == "collisions":
        candidate_index = _collision_set(df, pid_idx, loose_idx)
    elif scope == "all":
        candidate_index = df.index
    else:
        raise ValueError(f"unknown scope: {scope}")

    if len(candidate_index) == 0:
        return {
            "status": "no_collision_rows",
            "n_pool": len(df),
            "n_pid_collisions": n_pid_collisions,
            "n_loose_collisions": n_loose_collisions,
        }

    test = df.loc[candidate_index]
    if sample_size is not None and sample_size < len(test):
        test = test.sample(n=sample_size, random_state=seed)

    buckets: dict[str, dict[str, int]] = {}
    disagreements: list[dict] = []
    residual = 0

    for test_pos, truth_row in test.iterrows():
        truth = truth_row.to_dict()
        pid = truth.get("product_identity_key")
        loose = truth.get("canonical_loose")
        country = truth.get("country")

        # Tier 1: same pid, different row
        buddy_pos: Optional[int] = None
        method: Optional[str] = None
        if isinstance(pid, str) and pid:
            for p in pid_idx.get(pid, []):
                if p != test_pos:
                    buddy_pos = p
                    method = "product_identity_key"
                    break
        # Tier 2: same loose+country, different row
        if buddy_pos is None and isinstance(loose, str) and loose and country:
            for p in loose_idx.get((loose, country), []):
                if p != test_pos:
                    buddy_pos = p
                    method = "canonical_loose"
                    break

        if buddy_pos is None or method is None:
            residual += 1
            continue

        predicted = df.loc[buddy_pos].to_dict()
        b = buckets.setdefault(method, {"matched": 0, "agreed": 0})
        b["matched"] += 1
        if _payload_eq(predicted, truth):
            b["agreed"] += 1
        else:
            disagreements.append(
                {
                    "input_hash": truth.get("input_hash"),
                    "tier": method,
                    "country": truth.get("country"),
                    "predicted_coicop": predicted.get("coicop_code"),
                    "truth_coicop": truth.get("coicop_code"),
                    "predicted_sub_label": predicted.get("sub_label_id"),
                    "truth_sub_label": truth.get("sub_label_id"),
                    "predicted_pricing_basis": predicted.get("pricing_basis"),
                    "truth_pricing_basis": truth.get("pricing_basis"),
                    "predicted_standard_unit": predicted.get("standard_unit"),
                    "truth_standard_unit": truth.get("standard_unit"),
                    "predicted_state": predicted.get("state"),
                    "truth_state": truth.get("state"),
                }
            )

    return {
        "status": "ok",
        "n_pool": len(df),
        "n_pid_collisions": n_pid_collisions,
        "n_loose_collisions": n_loose_collisions,
        "n_test": len(test),
        "n_residual": residual,
        "buckets": buckets,
        "disagreements": disagreements,
    }


def render_report(
    result: dict[str, Any],
    seed: int,
    sample_size: Optional[int],
    scope: str,
) -> str:
    lines = [
        "# Cascade replay report",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- seed: {seed}",
        f"- sample_size: {sample_size if sample_size is not None else 'all'}",
        f"- scope: {scope}",
        "- mode: leave-one-out (LLM tier disabled)",
    ]
    if result["status"] != "ok":
        lines.append("")
        lines.append(f"status: **{result['status']}**")
        if "n_pool" in result:
            lines.append(f"- n_pool: {result['n_pool']}")
            lines.append(f"- pid collisions in pool: {result['n_pid_collisions']}")
            lines.append(
                f"- loose+country collisions in pool: {result['n_loose_collisions']}"
            )
        return "\n".join(lines)
    lines.extend(
        [
            f"- n_pool (replayable rows): {result['n_pool']}",
            f"- pid collisions in pool: {result['n_pid_collisions']}",
            f"- loose+country collisions in pool: {result['n_loose_collisions']}",
            f"- n_test: {result['n_test']}",
            f"- n_residual (no buddy found → would fire LLM): {result['n_residual']}",
            "",
            "## Per-tier agreement (leave-one-out)",
            "",
            "| tier | matched | agreed | rate |",
            "|---|---|---|---|",
        ]
    )
    for tier, b in sorted(result["buckets"].items()):
        rate = b["agreed"] / b["matched"] if b["matched"] else 0.0
        lines.append(f"| {tier} | {b['matched']} | {b['agreed']} | {rate:.3%} |")
    return "\n".join(lines)


def write_outputs(
    result: dict[str, Any],
    seed: int,
    sample_size: Optional[int],
    scope: str,
    output_dir: Path,
) -> tuple[Path, Optional[Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "_cascade_replay_report.md"
    report_path.write_text(render_report(result, seed, sample_size, scope))
    disagreement_path: Optional[Path] = None
    if result.get("disagreements"):
        disagreement_path = output_dir / "disagreements.parquet"
        pd.DataFrame(result["disagreements"]).to_parquet(disagreement_path, index=False)
    return report_path, disagreement_path
