"""Dimension-table materialization.

Reads `products_input.parquet`, applies `normalize.canonicalize` per row,
groups rows by `(country, canonical_strict)` into a product dimension.
Writes `data/prices/_enrich/products.parquet`.

The output `product_identity_key` is what later stages (match cascade) use
as Tier 1 cache key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.normalize import CanonicalProduct, canonicalize


def _canonicalize_row(row: pd.Series) -> CanonicalProduct:
    return canonicalize(
        item_name=row.get("product_name_original") or "",
        category=row.get("category") or None,
        country=row.get("country") or "",
        lang=row.get("lang") or None,
    )


def dedupe(prepared: pd.DataFrame) -> pd.DataFrame:
    if prepared.empty:
        return pd.DataFrame(
            columns=[
                "product_identity_key",
                "canonical_loose",
                "country",
                "lang",
                "brand",
                "count",
                "value",
                "unit",
                "category",
                "currency",
                "channel",
                "declared_coicop_codes",
                "first_name",
                "price",
                "n_observations",
                "n_input_hashes",
                "input_hashes",
            ]
        )

    canon = prepared.apply(_canonicalize_row, axis=1)
    df = prepared.copy()
    df["product_identity_key"] = [c.canonical_strict for c in canon]
    df["canonical_loose"] = [c.canonical_loose for c in canon]
    df["brand"] = [c.brand for c in canon]
    df["count"] = [c.count for c in canon]
    df["value"] = [c.value for c in canon]
    df["unit"] = [c.unit for c in canon]

    # Rows that canonicalize to empty (e.g. all-stop-word inputs) keep their
    # input_hash as identity so they don't collapse into a single bucket.
    empty_mask = df["product_identity_key"] == ""
    df.loc[empty_mask, "product_identity_key"] = "__empty__:" + df.loc[
        empty_mask, "input_hash"
    ].astype(str)

    if "declared_coicop_codes" not in df.columns:
        df["declared_coicop_codes"] = ""
    if "channel" not in df.columns:
        df["channel"] = ""

    grouped = df.groupby(["country", "product_identity_key"], as_index=False).agg(
        canonical_loose=("canonical_loose", "first"),
        lang=("lang", "first"),
        brand=("brand", "first"),
        count=("count", "first"),
        value=("value", "first"),
        unit=("unit", "first"),
        category=("category", "first"),
        currency=("currency", "first"),
        channel=("channel", "first"),
        declared_coicop_codes=("declared_coicop_codes", "first"),
        first_name=("product_name_original", "first"),
        price=("price", "median"),
        n_observations=("n_rows", "sum"),
        n_input_hashes=("input_hash", "nunique"),
        input_hashes=("input_hash", lambda s: sorted(set(s))),
    )
    return grouped


def run(
    prepared_path: Optional[Path] = None, products_path: Optional[Path] = None
) -> pd.DataFrame:
    prepared_path = prepared_path or config.PRODUCTS_INPUT_PARQUET
    products_path = products_path or config.PRODUCTS_PARQUET
    prepared = pd.read_parquet(prepared_path)
    products = dedupe(prepared)
    products_path.parent.mkdir(parents=True, exist_ok=True)
    products.to_parquet(products_path, index=False)
    return products
