"""Orchestrate a gold eval run: cascade -> predictions -> score -> report."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import cache, config
from prices.enrich import index as tier_b_index
from prices.enrich.eval import gold as gold_mod
from prices.enrich.eval import report as report_mod
from prices.enrich.eval.gold import SYNTH_PREFIX
from prices.enrich.eval.metrics import PAYLOAD_FIELDS, score
from prices.enrich.stages import enrich as enrich_mod
from prices.enrich.stages.enrich import cascade

DEFAULT_OUT_DIR = config.REPO_ROOT / "outputs" / "prices" / "reports" / "eval"

_CACHE_KEYS = (
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "coicop_code",
    "sub_label_id",
)


def _payload_from_cache_row(row: dict) -> dict:
    return {k: row.get(k) for k in PAYLOAD_FIELDS}


def _payload_from_residual_row(rr) -> dict:
    payload = {f: None for f in PAYLOAD_FIELDS}
    for f in ("pricing_basis", "standard_unit", "amount_value", "count", "multiplier"):
        col = f"tier_a_{f}"
        if col in rr.index:
            payload[f] = rr.get(col)
    return payload


def _build_predictions(
    products: pd.DataFrame,
    cache_rows: list[dict],
    residual: pd.DataFrame,
    captured: Optional[list[dict]] = None,
) -> dict:
    by_synth: dict[str, dict] = {}
    for row in cache_rows + (captured or []):
        h = row.get("input_hash")
        if isinstance(h, str) and h.startswith(SYNTH_PREFIX):
            by_synth[h] = row

    residual_by_rid: dict[str, dict] = {}
    if not residual.empty:
        for _, rr in residual.iterrows():
            residual_by_rid[str(rr["row_id"])] = _payload_from_residual_row(rr)

    predictions: dict[str, dict] = {}
    for _, prod in products.iterrows():
        rid = str(prod["row_id"])
        hit = by_synth.get(f"{SYNTH_PREFIX}{rid}")
        if hit is not None:
            predictions[rid] = {
                "match_method": str(hit.get("match_method") or "unknown"),
                "payload": _payload_from_cache_row(hit),
            }
        else:
            predictions[rid] = {
                "match_method": "residual_llm",
                "payload": residual_by_rid.get(rid, {f: None for f in PAYLOAD_FIELDS}),
            }
    return predictions


def _miss_subreason(v: dict) -> str:
    """Split the overloaded `miss` reason into a fix-actionable sub-bucket.

    `miss` is returned both when no neighbor survives the channel/distance
    filter (top1_cosine 0 -> coverage gap) and when neighbors exist but clear
    neither the hard nor soft gate (distance vs. disagreement). The fix differs:
    coverage/distance -> anchors or e5-large; disagreement -> not synonyms.
    """
    cos = v["top1_cosine"]
    if cos <= 0.0:
        return "miss:no_neighbor"
    hard_min = config.knn_score_hard_min(config.E5_MODEL_PATH)
    if cos < hard_min:
        return "miss:below_hard_cos"
    if v["top1_agree"] < config.KNN_CLUSTER_AGREEMENT_MIN:
        return "miss:low_agreement"
    return "miss:soft_thin"


def _residual_reasons(residual: pd.DataFrame, verdicts: dict[str, dict]) -> dict:
    """Histogram the deterministic residual set by why tier-b didn't fire.

    `verdicts` maps row_id -> tier-b hit fields teed from _tier_b_dispatch.
    Rows tier-b accepted but the cascade still dropped (killswitch / unguarded
    basis mismatch) are bucketed as post_accept_veto. The catch-all `miss`
    reason is split via _miss_subreason so coverage gaps are distinguishable
    from distance and disagreement.
    """
    counts: Counter = Counter()
    if residual.empty:
        return {}
    for rid in residual["row_id"].astype(str).tolist():
        v = verdicts.get(rid)
        if v is None:
            counts["unknown"] += 1
        elif v["accepted"]:
            counts["post_accept_veto"] += 1
        elif v["escalation_reason"] == "miss":
            counts[_miss_subreason(v)] += 1
        else:
            counts[v["escalation_reason"] or "unknown"] += 1
    return dict(counts.most_common())


def _run_tier_c_capture(residual: pd.DataFrame) -> list[dict]:
    import asyncio

    from prices.enrich.stages import tier_c

    tier_c.L1_CACHE.clear()
    captured: list[dict] = []
    orig_append = cache.append_enrichments
    cache.append_enrichments = lambda rows: captured.extend(rows)
    try:
        asyncio.run(tier_c.run_residual(residual))
    finally:
        cache.append_enrichments = orig_append
    return captured


def run(
    gold_path: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    run_tier_c: bool = False,
    write: bool = True,
    print_report: bool = False,
) -> dict:
    gold = gold_mod.load_gold(gold_path)
    products = gold_mod.build_products(gold)
    cached = cache.read_cache()
    # Eval is read-only w.r.t. production data: the cascade's only write side
    # effect is tier-b miss logging, which we suppress here. We also tee
    # _tier_b_dispatch to record each row's tier-b verdict + escalation_reason
    # (the residual reason is otherwise only logged for the `miss` subset).
    verdicts: dict[str, dict] = {}
    orig_dispatch = enrich_mod._tier_b_dispatch

    def _capturing_dispatch(*a, **k):
        hit = orig_dispatch(*a, **k)
        prod = k.get("product")
        if prod is not None:
            verdicts[str(prod.get("row_id"))] = {
                "accepted": bool(hit.accepted),
                "escalation_reason": str(hit.escalation_reason or ""),
                "top1_cosine": float(hit.top1_cosine or 0.0),
                "top1_agree": float(hit.top1_cluster_agreement or 0.0),
                "topk_majority": int(hit.topk_majority or 0),
            }
        return hit

    orig_append_miss = tier_b_index.append_miss
    tier_b_index.append_miss = lambda *a, **k: None
    enrich_mod._tier_b_dispatch = _capturing_dispatch
    try:
        cache_rows, residual, _match_log, _cross_check = cascade(products, cached)
    finally:
        tier_b_index.append_miss = orig_append_miss
        enrich_mod._tier_b_dispatch = orig_dispatch

    captured = _run_tier_c_capture(residual) if run_tier_c else None
    predictions = _build_predictions(products, cache_rows, residual, captured)

    result = score(predictions, gold)
    result["n_total"] = len(gold)
    result["n_cache"] = int(len(cached))
    result["tier_c"] = bool(run_tier_c)
    result["n_residual"] = int(len(residual))
    result["residual_reasons"] = _residual_reasons(residual, verdicts)

    report_md = report_mod.render(result)
    if print_report:
        print("\n" + report_md)
    if write:
        out_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
        result["report_path"] = str(report_mod.write(result, report_md, out_dir))
    return result
