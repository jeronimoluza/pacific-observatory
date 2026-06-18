"""Per-field, unit_value, and A/B/C causal-bucket scoring."""

from __future__ import annotations

from collections import Counter

import pandas as pd

from prices.enrich.eval.gold import CATEGORICAL_FIELDS, CATEGORICAL_MAP, MAGNITUDE_MAP
from prices.enrich.stages.merge import compute_unit_value

UNIT_VALUE_TOL = 0.01  # 1% relative; beyond this counts as wrong
REF_PRICE = 1.0  # constant — unit_value ratio is price-independent

PAYLOAD_FIELDS = (*CATEGORICAL_FIELDS, "amount_value", "count", "multiplier")

# A_coicop > B_basis > C_magnitude > ok (first failing stage wins)
BUCKETS = ("A_coicop", "B_basis", "C_magnitude", "ok")


def _norm_str(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s or None


def _categorical_eq(pred, truth) -> bool:
    p, t = _norm_str(pred), _norm_str(truth)
    if p is None and t is None:
        return True
    if p is None or t is None:
        return False
    return p == t


def _unit_value(basis, amount_value, count, multiplier):
    return compute_unit_value(REF_PRICE, basis, amount_value, count, multiplier)


def unit_value_ok(pred_uv, gold_uv, tol: float = UNIT_VALUE_TOL) -> bool:
    if pred_uv is None and gold_uv is None:
        return True
    if pred_uv is None or gold_uv is None:
        return False
    if gold_uv == 0:
        return pred_uv == 0
    return abs(pred_uv - gold_uv) / abs(gold_uv) <= tol


def _truth_row(gold_row) -> dict:
    cat = {field: gold_row.get(col) for col, field in CATEGORICAL_MAP.items()}
    mag = {field: gold_row.get(col) for col, field in MAGNITUDE_MAP.items()}
    return {**cat, "_mag": mag}


def evaluate_rows(predictions: dict, gold: pd.DataFrame) -> list[dict]:
    """One record per gold row: field correctness, unit_value match, bucket."""
    records: list[dict] = []
    for _, gr in gold.iterrows():
        rid = str(gr["row_id"])
        truth = _truth_row(gr)
        pred = predictions.get(rid)
        payload = (pred or {}).get("payload", {})
        method = (pred or {}).get("match_method", "missing")

        field_ok = {
            f: _categorical_eq(payload.get(f), truth.get(f)) for f in CATEGORICAL_FIELDS
        }

        gold_uv = _unit_value(
            truth["pricing_basis"],
            truth["_mag"]["amount_value"],
            truth["_mag"]["count"],
            truth["_mag"]["multiplier"],
        )
        pred_uv = _unit_value(
            payload.get("pricing_basis"),
            payload.get("amount_value"),
            payload.get("count"),
            payload.get("multiplier"),
        )
        uv_ok = unit_value_ok(pred_uv, gold_uv)

        if not field_ok["coicop_code"]:
            bucket = "A_coicop"
        elif not field_ok["pricing_basis"]:
            bucket = "B_basis"
        elif not uv_ok:
            bucket = "C_magnitude"
        else:
            bucket = "ok"

        records.append(
            {
                "row_id": rid,
                "match_method": method,
                "labeler_model": str(gr.get("labeler_model", "")),
                "country": str(gr.get("country", "")),
                "field_ok": field_ok,
                "unit_value_ok": uv_ok,
                "gold_unit_value": gold_uv,
                "pred_unit_value": pred_uv,
                "bucket": bucket,
            }
        )
    return records


def aggregate(records: list[dict]) -> dict:
    """Accuracy block over a (sub)set of per-row records."""
    n = len(records)
    field_acc = {f: sum(r["field_ok"][f] for r in records) for f in CATEGORICAL_FIELDS}
    uv_correct = sum(r["unit_value_ok"] for r in records)
    buckets = Counter(r["bucket"] for r in records)
    return {
        "n": n,
        "fields": {f: [field_acc[f], n] for f in CATEGORICAL_FIELDS},
        "unit_value": [uv_correct, n],
        "buckets": {b: buckets.get(b, 0) for b in BUCKETS},
    }


def _group(records: list[dict], key: str) -> dict:
    out: dict[str, dict] = {}
    keys = sorted({r[key] for r in records})
    for k in keys:
        out[k] = aggregate([r for r in records if r[key] == k])
    return out


def score(predictions: dict, gold: pd.DataFrame) -> dict:
    records = evaluate_rows(predictions, gold)
    return {
        "overall": aggregate(records),
        "by_tier": _group(records, "match_method"),
        "by_labeler": _group(records, "labeler_model"),
        "records": records,
    }
