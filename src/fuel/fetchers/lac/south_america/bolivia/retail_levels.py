"""Bolivia domestic retail pump prices from the hand-curated table configs/_manual/bo_retail_levels.yaml.

Each row of the table is the price for Bolivian-plated vehicles (Bs per
litre; GNV Bs/m3; GLP Bs per 10 kg garrafa) with its effective date, legal
instrument, source document (URL, archive URL, sha256 of the stored file)
and confidence. Nothing is scraped: ANH publishes these only as images.
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
    / "bo_retail_levels.yaml"
)


def fetch_bo_retail_levels(cutoff: date) -> pd.DataFrame | None:
    levels = yaml.safe_load(_TABLE.read_text(encoding="utf-8"))["levels"]
    rows = [
        {
            "observation_date": str(r["effective"]),
            "country": "Bolivia",
            "fuel_product": r["product"],
            "price_local": r["bs"],
            "currency": "BOB",
            "unit": r["unit"],
            "source_key": "bo_retail_levels",
        }
        for r in levels
        if r.get("bs") is not None and pd.Timestamp(r["effective"]).date() > cutoff
    ]
    return pd.DataFrame(rows) if rows else None


__all__ = ["fetch_bo_retail_levels"]
