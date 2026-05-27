from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import cache, config
from prices.enrich.stages.prepare import _row_input_dict
from prices.enrich.versioning import input_hash

ENRICHMENT_COLS = [
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "coicop_code",
    "sub_label_id",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
    "confidence",
    "state",
    "dimensions_json",
]


def _coerce_count(value) -> int:
    if value is None or pd.isna(value):
        return 1
    return int(value)


def compute_unit_value(
    price, basis, amount_value, count, multiplier
) -> Optional[float]:
    if price is None or pd.isna(price):
        return None
    if basis is None or (not isinstance(basis, str) and pd.isna(basis)):
        return None
    c = _coerce_count(count)
    m = _coerce_count(multiplier)
    if basis in ("mass", "volume", "length"):
        if amount_value is None or pd.isna(amount_value) or amount_value == 0:
            return None
        denom = float(amount_value) * c * m
        if denom == 0:
            return None
        return float(price) / denom
    if basis in ("count", "item"):
        denom = c * m
        if denom == 0:
            return None
        return float(price) / denom
    return None


def merge_enrichments(
    raw: pd.DataFrame,
    enriched: pd.DataFrame,
    key_recompute: bool = True,
) -> pd.DataFrame:
    raw = raw.copy()
    if key_recompute:
        raw["input_hash"] = raw.apply(lambda r: input_hash(_row_input_dict(r)), axis=1)
    if enriched.empty:
        merged = raw.copy()
        for col in ENRICHMENT_COLS:
            merged[col] = pd.NA
    else:
        keep_cols = [c for c in ENRICHMENT_COLS if c in enriched.columns]
        join_cols = (
            ["input_hash"] + keep_cols
            if "input_hash" in enriched.columns
            else keep_cols
        )
        merged = raw.merge(enriched[join_cols], on="input_hash", how="left")
    merged["unit_value"] = merged.apply(
        lambda r: compute_unit_value(
            r.get("price"),
            r.get("pricing_basis"),
            r.get("amount_value"),
            r.get("count"),
            r.get("multiplier"),
        ),
        axis=1,
    )
    if "input_hash" in merged.columns:
        merged = merged.drop(columns=["input_hash"])
    return merged


def run(csv_path: Optional[Path] = None) -> None:
    csv_path = csv_path or config.RAW_PRICES_CSV
    raw = pd.read_csv(csv_path, low_memory=False)
    enriched = cache.read_cache()
    out = merge_enrichments(raw, enriched, key_recompute=True)
    out.to_csv(csv_path, index=False)
    print(f"Wrote {len(out)} rows to {csv_path}")
