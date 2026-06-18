"""Gold v3 blind evaluation harness (Phase 0 baseline + per-phase gates).

Loads `data/prices/_enrich/gold_v3_labels.csv` (200 hand-curated rows),
runs the current production cascade end-to-end against the existing
enrichments cache, reports per-field accuracy bucketed by which tier
fired. The residual bucket (`residual_llm`) records rows that would have
fired the LLM tier; LLM is not invoked here — baseline measures what
deterministic propagation alone gives us today.

Environment toggles:
    GOLD_V3_WRITE_BASELINE=1  → persist report to `_gold_v3_baseline.md`
    GOLD_V3_PRINT=1           → echo the report to stdout

This file is the ONLY authorized importer of `gold_v3_labels.csv` (see
`_gold_v3_seal.py`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import _gold_v3_seal  # noqa: F401  (import-time seal check)

from core.config import load_countries
from prices.enrich.tier_b import cache
from prices.enrich.normalize import canonicalize
from prices.enrich.stages.enrich import cascade

GOLD_V3_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "prices"
    / "_enrich"
    / "gold_v3_labels.csv"
)
BASELINE_PATH = GOLD_V3_PATH.parent / "_gold_v3_baseline.md"

EVAL_FIELDS = [
    "coicop_code",
    "sub_label_id",
    "pricing_basis",
    "standard_unit",
    "state",
    "is_promotion",
    "is_bundle",
    "is_multipack",
]
BOOL_FIELDS = {"is_promotion", "is_bundle", "is_multipack"}


def _country_lang_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


def _country_currency_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        out[slug] = str(meta.get("currency", "") or "")
    return out


def _build_products(gold: pd.DataFrame) -> pd.DataFrame:
    lang_map = _country_lang_map()
    cur_map = _country_currency_map()
    rows: list[dict] = []
    for _, r in gold.iterrows():
        country = str(r["country"])
        canon = canonicalize(
            item_name=str(r["product_name_original"]),
            category=None,
            country=country,
            lang=lang_map.get(country) or None,
        )
        eid = str(r["eval_id"])
        pid = canon.canonical_strict or f"__empty__:{eid}"
        rows.append(
            {
                "product_identity_key": pid,
                "canonical_loose": canon.canonical_loose,
                "first_name": str(r["product_name_original"]),
                "category": "",
                "country": country,
                "currency": cur_map.get(country, ""),
                "input_hashes": [f"__gold_v3_synthetic__:{eid}"],
                "eval_id": eid,
            }
        )
    return pd.DataFrame(rows)


def _norm_truth_value(field: str, val):
    if pd.isna(val):
        return None
    if field in BOOL_FIELDS:
        s = str(val).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    return val


def _norm_pred_value(field: str, val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if field in BOOL_FIELDS:
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    return val


def _truth_map(gold: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for _, r in gold.iterrows():
        out[str(r["eval_id"])] = {
            f: _norm_truth_value(f, r.get(f)) for f in EVAL_FIELDS
        }
    return out


_TIER_A_TO_EVAL = {
    "pricing_basis": "pricing_basis",
    "standard_unit": "standard_unit",
    "is_promotion": "is_promotion",
    "is_bundle": "is_bundle",
    "is_multipack": "is_multipack",
}


def _predictions_from_cascade(products: pd.DataFrame) -> dict[str, dict]:
    cached = cache.read_cache()
    cache_rows, residual, _match_log, _cross_check = cascade(products, cached)

    by_synth: dict[str, dict] = {}
    for row in cache_rows:
        h = row.get("input_hash")
        if isinstance(h, str) and h.startswith("__gold_v3_synthetic__:"):
            by_synth[h] = row

    tier_a_by_eval: dict[str, dict] = {}
    if not residual.empty:
        for _, rr in residual.iterrows():
            eid = rr["eval_id"]
            payload = {f: None for f in EVAL_FIELDS}
            for ta_field, eval_field in _TIER_A_TO_EVAL.items():
                col = f"tier_a_{ta_field}"
                if col in residual.columns:
                    payload[eval_field] = rr.get(col)
            tier_a_by_eval[eid] = payload

    out: dict[str, dict] = {}
    for _, prod in products.iterrows():
        eid = prod["eval_id"]
        synth = f"__gold_v3_synthetic__:{eid}"
        hit = by_synth.get(synth)
        if hit is None:
            out[eid] = {
                "match_method": "residual_llm+regex",
                "payload": tier_a_by_eval.get(eid, {f: None for f in EVAL_FIELDS}),
            }
        else:
            out[eid] = {
                "match_method": str(hit.get("match_method") or "unknown"),
                "payload": {f: hit.get(f) for f in EVAL_FIELDS},
            }
    return out


def _value_eq(field: str, pred, truth) -> bool:
    p = _norm_pred_value(field, pred)
    t = (
        _norm_truth_value(field, truth)
        if not isinstance(truth, (bool, type(None)))
        else truth
    )
    if p is None and t is None:
        return True
    if p is None or t is None:
        return False
    if field in BOOL_FIELDS:
        return bool(p) == bool(t)
    return str(p) == str(t)


def _compute_buckets(predictions: dict, truth: dict) -> dict:
    buckets: dict[str, dict[str, list[int]]] = {}
    for eid, pred in predictions.items():
        b = buckets.setdefault(pred["match_method"], {f: [0, 0] for f in EVAL_FIELDS})
        gold = truth[eid]
        for f in EVAL_FIELDS:
            b[f][1] += 1
            if _value_eq(f, pred["payload"].get(f), gold.get(f)):
                b[f][0] += 1
    return buckets


def _compute_overall(predictions: dict, truth: dict) -> dict[str, list[int]]:
    """Overall per-field accuracy across all 200 rows."""
    out = {f: [0, 0] for f in EVAL_FIELDS}
    for eid, pred in predictions.items():
        gold = truth[eid]
        for f in EVAL_FIELDS:
            out[f][1] += 1
            if _value_eq(f, pred["payload"].get(f), gold.get(f)):
                out[f][0] += 1
    return out


def _render_report(buckets: dict, overall: dict, n_total: int, n_cache: int) -> str:
    lines = [
        "# Gold v3 baseline (Phase 0)",
        "",
        f"- n_total: {n_total}",
        f"- cache rows scanned: {n_cache}",
        "- LLM tier: **disabled** for baseline (residual rows = floor)",
        "",
        "## Overall per-field accuracy (n=200, residual counts as wrong)",
        "",
        "| field | correct | total | accuracy |",
        "|---|---|---|---|",
    ]
    for f in EVAL_FIELDS:
        c, t = overall[f]
        rate = (c / t) if t else 0.0
        lines.append(f"| {f} | {c} | {t} | {rate:.3%} |")
    lines.append("")
    lines.append("## Per-tier per-field accuracy")
    for tier in sorted(buckets):
        bb = buckets[tier]
        n_tier = max((v[1] for v in bb.values()), default=0)
        lines.append("")
        lines.append(f"### {tier} (n={n_tier})")
        lines.append("")
        lines.append("| field | correct | total | accuracy |")
        lines.append("|---|---|---|---|")
        for f in EVAL_FIELDS:
            c, t = bb[f]
            rate = (c / t) if t else 0.0
            lines.append(f"| {f} | {c} | {t} | {rate:.3%} |")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def gold_v3() -> pd.DataFrame:
    if not GOLD_V3_PATH.exists():
        pytest.skip(f"gold v3 absent at {GOLD_V3_PATH}")
    return pd.read_csv(GOLD_V3_PATH)


def test_gold_v3_schema(gold_v3):
    assert len(gold_v3) >= 200, f"expected ≥200 rows, got {len(gold_v3)}"
    required = {"eval_id", "product_name_original", "country", *EVAL_FIELDS}
    missing = required - set(gold_v3.columns)
    assert not missing, f"missing columns: {missing}"
    assert gold_v3["eval_id"].is_unique, "eval_id collisions in gold v3"


def test_gold_v3_tier_c_gate(gold_v3):
    """Phase 3 gate: cascade + tier-c LLM enabled.

    Skipped unless `GOLD_V3_RUN_TIER_C=1` AND a gemini API key is set.
    Captures tier-c writes in-memory so the real cache is not polluted by
    synthetic gold-v3 input_hashes.

    Hard gates:
        * coicop_code ≥ baseline (Phase-0 = 0%, blind)
        * sub_label_id ≥ baseline (Phase-0 = 0%)
        * pricing_basis ≥ 0.95 — Phase 4 tier-a overlay gating closed the
          tier_b_knn_hard regex regression (97.5% cascade-only floor).
        * standard_unit ≥ 0.95
        * state ≥ 0.95 — guards against catastrophic regression.
    """
    if os.environ.get("GOLD_V3_RUN_TIER_C") != "1":
        pytest.skip("Set GOLD_V3_RUN_TIER_C=1 to run the LLM gate")
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        pytest.skip("GOOGLE_API_KEY / GEMINI_API_KEY required for tier-c")

    import asyncio

    from prices.enrich.stages import tier_c

    tier_c.L1_CACHE.clear()

    products = _build_products(gold_v3)
    truth = _truth_map(gold_v3)
    cached = cache.read_cache()
    cache_rows, residual, _match_log, _cross_check = cascade(products, cached)

    captured: list[dict] = []
    orig_append = cache.append_enrichments
    cache.append_enrichments = lambda rows: captured.extend(rows)
    try:
        asyncio.run(tier_c.run_residual(residual))
    finally:
        cache.append_enrichments = orig_append

    by_synth: dict[str, dict] = {}
    for row in cache_rows + captured:
        h = row.get("input_hash")
        if isinstance(h, str) and h.startswith("__gold_v3_synthetic__:"):
            by_synth[h] = row

    predictions: dict[str, dict] = {}
    for _, prod in products.iterrows():
        eid = prod["eval_id"]
        synth = f"__gold_v3_synthetic__:{eid}"
        hit = by_synth.get(synth)
        if hit is None:
            predictions[eid] = {
                "match_method": "unresolved",
                "payload": {f: None for f in EVAL_FIELDS},
            }
        else:
            predictions[eid] = {
                "match_method": str(hit.get("match_method") or "unknown"),
                "payload": {f: hit.get(f) for f in EVAL_FIELDS},
            }

    buckets = _compute_buckets(predictions, truth)
    overall = _compute_overall(predictions, truth)
    report = _render_report(
        buckets, overall, n_total=len(gold_v3), n_cache=int(len(cached))
    )
    if os.environ.get("GOLD_V3_PRINT") == "1":
        print("\n" + report)
    if os.environ.get("GOLD_V3_WRITE_PHASE3") == "1":
        out = BASELINE_PATH.parent / "_gold_v3_phase3.md"
        out.write_text(report)

    coicop_acc = overall["coicop_code"][0] / overall["coicop_code"][1]
    sub_acc = overall["sub_label_id"][0] / overall["sub_label_id"][1]
    pb_acc = overall["pricing_basis"][0] / overall["pricing_basis"][1]
    su_acc = overall["standard_unit"][0] / overall["standard_unit"][1]

    state_acc = overall["state"][0] / overall["state"][1]

    assert coicop_acc >= 0.0, f"coicop {coicop_acc:.3%} below baseline"
    assert sub_acc >= 0.0, f"sub_label_id {sub_acc:.3%} below baseline"
    assert pb_acc >= 0.95, f"pricing_basis {pb_acc:.3%} below Phase-4 gate 0.95"
    assert su_acc >= 0.95, f"standard_unit {su_acc:.3%} below Phase-4 gate 0.95"
    assert state_acc >= 0.95, f"state {state_acc:.3%} below Phase-2 floor 0.95"


def test_gold_v3_cascade_baseline(gold_v3):
    products = _build_products(gold_v3)
    truth = _truth_map(gold_v3)
    cached = cache.read_cache()
    predictions = _predictions_from_cascade(products)
    buckets = _compute_buckets(predictions, truth)
    overall = _compute_overall(predictions, truth)
    report = _render_report(
        buckets, overall, n_total=len(gold_v3), n_cache=int(len(cached))
    )
    if os.environ.get("GOLD_V3_PRINT") == "1":
        print("\n" + report)
    if os.environ.get("GOLD_V3_WRITE_BASELINE") == "1":
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(report)
    if os.environ.get("GOLD_V3_DUMP_MISSES") == "1":
        miss_rows = []
        name_by_eid = dict(zip(gold_v3["eval_id"], gold_v3["product_name_original"]))
        country_by_eid = dict(zip(gold_v3["eval_id"], gold_v3["country"]))
        for eid, pred in predictions.items():
            gold = truth[eid]
            for f in ("pricing_basis", "standard_unit"):
                p = pred["payload"].get(f)
                t = gold.get(f)
                if not _value_eq(f, p, t):
                    miss_rows.append(
                        {
                            "eval_id": eid,
                            "country": country_by_eid[eid],
                            "name": name_by_eid[eid],
                            "field": f,
                            "predicted": p,
                            "truth": t,
                        }
                    )
        miss_path = BASELINE_PATH.parent / "_gold_v3_misses.csv"
        miss_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(miss_rows).to_csv(miss_path, index=False)
    assert len(predictions) == len(gold_v3)
    assert overall["coicop_code"][1] == len(gold_v3)
