"""Ecuador retail pump prices from the hand-curated table configs/_manual/ec_retail_levels.yaml.

Each row of the table is a precio de venta al público (USD per gallon; GLP
USD per 15 kg cylinder) with its effective date, source document (URL,
archive URL, sha256 of the stored file) and confidence. Nothing is scraped:
ARCH's site is down and prices are published by communiqué and press.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

_TABLE = (
    Path(__file__).resolve().parents[4]
    / "configs"
    / "_manual"
    / "ec_retail_levels.yaml"
)


def fetch_ec_retail_levels(cutoff: date) -> pd.DataFrame | None:
    levels = yaml.safe_load(_TABLE.read_text(encoding="utf-8"))["levels"]
    rows = [
        {
            "observation_date": str(r["effective"]),
            "country": "Ecuador",
            "fuel_product": r["product"],
            "price_local": r["usd"],
            "currency": "USD",
            "unit": "KG15" if r["product"].startswith("GLP") else "GAL",
            "source_key": "ec_retail_levels",
        }
        for r in levels
        if r.get("usd") is not None and pd.Timestamp(r["effective"]).date() > cutoff
    ]
    return pd.DataFrame(rows) if rows else None


__all__ = ["fetch_ec_retail_levels"]
