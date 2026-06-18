from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.tier_b import cache
from prices.enrich.stages.prepare import _row_input_dict, parse_price
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
    "trust_level",
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
    # Workaround for pre-fix enrichment rows where the model
    # double-counted the multipack: count == multiplier > 1 AND
    # amount_value was set to the pack-total instead of per-unit.
    # Collapse to a single factor so denom matches the as-paid qty.
    if c == m and c > 1:
        if basis in ("mass", "volume", "length"):
            c = 1
            m = 1
        else:
            m = 1
    # Sachet-pack double-encode: amount_value holds the pack-total
    # mass/volume while count was filled with the piece count
    # (e.g. 100 × 21g latte sachets → av=2.1, count=100). Trust the
    # pack-total and collapse count. 0.5 (kg/lt) excludes any plausible
    # per-piece F&B SKU so single-bottle rows are unaffected.
    elif (
        basis in ("mass", "volume", "length")
        and c > 1
        and m == 1
        and amount_value is not None
        and not pd.isna(amount_value)
        and float(amount_value) >= 0.5
    ):
        c = 1
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
        enriched = enriched.copy()
        if "input_hash" not in enriched.columns:
            enriched["input_hash"] = enriched.apply(
                lambda r: input_hash(
                    {
                        "product_name_original": str(r["product_name_original"]),
                        "category": ""
                        if pd.isna(r.get("category"))
                        else str(r["category"]),
                        "country": str(r["country"]),
                        "currency": str(r["currency"]),
                    }
                ),
                axis=1,
            )
        keep_cols = [c for c in ENRICHMENT_COLS if c in enriched.columns]
        join_cols = ["input_hash"] + keep_cols
        merged = raw.merge(enriched[join_cols], on="input_hash", how="left")
    # Legacy rows pre-dating the trust_level column default to high — they
    # were vetted under the prior pipeline and a NaN here would silently
    # drop them in any downstream trust filter.
    if "trust_level" in merged.columns:
        merged["trust_level"] = merged["trust_level"].fillna("high")
    elif "trust_level" in ENRICHMENT_COLS:
        merged["trust_level"] = "high"
    merged["price"] = merged.apply(
        lambda r: parse_price(r.get("price"), r.get("currency")), axis=1
    )
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


def run(csv_path: Optional[Path] = None, out_path: Optional[Path] = None) -> None:
    csv_path = csv_path or config.RAW_PRICES_CSV
    out_path = out_path or config.ENRICHED_PRICES_CSV
    raw = pd.read_csv(csv_path, low_memory=False)
    enriched = cache.read_cache()
    out = merge_enrichments(raw, enriched, key_recompute=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"Wrote {len(out)} rows to {out_path}")
