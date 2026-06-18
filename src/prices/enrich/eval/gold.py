"""Load the 500-row gold set and adapt it to cascade input."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import load_countries
from prices.enrich import config
from prices.enrich.normalize import canonicalize

GOLD_PATH = config.ENRICH_DIR / "gold_labels.parquet"

SYNTH_PREFIX = "__eval_synthetic__:"

# gold column -> categorical prediction field scored for exact match
CATEGORICAL_MAP = {
    "coicop_code_gold": "coicop_code",
    "sub_label_gold": "sub_label_id",
    "basis_gold": "pricing_basis",
    "unit_gold": "standard_unit",
}
CATEGORICAL_FIELDS = list(CATEGORICAL_MAP.values())

# gold column -> magnitude field feeding compute_unit_value
MAGNITUDE_MAP = {
    "basis_gold": "pricing_basis",
    "val_gold": "amount_value",
    "cnt_gold": "count",
    "mult_gold": "multiplier",
}

REQUIRED_COLS = {
    "row_id",
    "country",
    "product_name",
    "labeler_model",
    *CATEGORICAL_MAP,
    *MAGNITUDE_MAP,
}


def load_gold(path: Optional[Path] = None) -> pd.DataFrame:
    path = Path(path) if path else GOLD_PATH
    if not path.exists():
        raise FileNotFoundError(f"gold set absent at {path}")
    df = pd.read_parquet(path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"gold set missing columns: {sorted(missing)}")
    df = df.copy()
    df["row_id"] = df["row_id"].astype(str)
    if not df["row_id"].is_unique:
        raise ValueError("row_id collisions in gold set")
    return df


def _country_lang_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


def _country_currency_map() -> dict[str, str]:
    return {
        slug: str(meta.get("currency", "") or "")
        for slug, meta in load_countries().items()
    }


def build_products(gold: pd.DataFrame) -> pd.DataFrame:
    """Synthesise cascade-input products from gold rows.

    Mirrors the gold-v3 harness: each row gets a synthetic input_hash so
    tier-0/1/2 never spuriously hit the production cache, forcing predictions
    through live tier-a regex + tier-b KNN (and tier-c only when enabled).
    """
    lang_map = _country_lang_map()
    cur_map = _country_currency_map()
    rows: list[dict] = []
    for _, r in gold.iterrows():
        country = str(r["country"])
        name = str(r["product_name"])
        canon = canonicalize(
            item_name=name,
            category=None,
            country=country,
            lang=lang_map.get(country) or None,
        )
        rid = str(r["row_id"])
        rows.append(
            {
                "product_identity_key": canon.canonical_strict or f"__empty__:{rid}",
                "canonical_loose": canon.canonical_loose,
                "first_name": name,
                "category": "",
                "country": country,
                "currency": cur_map.get(country, ""),
                "input_hashes": [f"{SYNTH_PREFIX}{rid}"],
                "row_id": rid,
            }
        )
    return pd.DataFrame(rows)
