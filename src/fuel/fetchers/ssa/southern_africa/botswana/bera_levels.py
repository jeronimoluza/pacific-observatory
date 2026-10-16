"""Botswana BERA pump prices from the hand-curated table configs/_manual/bera_bw_levels.yaml.

Each row of the table is a price level in thebe/L with its effective date,
locality, source document (URL, archive URL, sha256 of the stored file) and
confidence. Rows with no level (a product's discontinuation) are skipped.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

_TABLE = (
    Path(__file__).resolve().parents[4] / "configs" / "_manual" / "bera_bw_levels.yaml"
)


def fetch_bera_bw_levels(cutoff: date) -> pd.DataFrame | None:
    levels = yaml.safe_load(_TABLE.read_text(encoding="utf-8"))["levels"]
    rows = [
        {
            "observation_date": str(r["effective"]),
            "country": "Botswana",
            "fuel_product": r["product"],
            "price_local": round(r["thebe"] / 100.0, 4),
            "currency": "BWP",
            "unit": "L",
            "source_key": "bera_bw_levels",
            "city": None if r["locality"] == "national" else r["locality"],
            "station_type": "national" if r["locality"] == "national" else "city",
        }
        for r in levels
        if r.get("thebe") is not None and pd.Timestamp(r["effective"]).date() > cutoff
    ]
    return pd.DataFrame(rows) if rows else None


__all__ = ["fetch_bera_bw_levels"]
