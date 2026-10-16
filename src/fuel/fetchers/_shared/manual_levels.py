"""Rows from a hand-curated price-level table, configs/_manual/<country>_levels.yaml.

Each table row is one level (effective date, product, locality, price_local) with its
source document (URL, archive URL, sha256 of the stored copy), method and confidence.
Rows without a price or with confidence "baja" are not emitted: they stay in the table
as evidence for `po fuel watch` only. "national" locality -> station_type national,
anything else -> the locality as city.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

MANUAL_DIR = Path(__file__).resolve().parents[2] / "configs" / "_manual"
_UNITS = {"liter": "L", "kilogram": "kg"}


def table_path(country_slug: str) -> Path:
    return MANUAL_DIR / f"{country_slug}_levels.yaml"


def read_manual_levels(table: Path, cutoff: date) -> pd.DataFrame | None:
    t = yaml.safe_load(table.read_text(encoding="utf-8"))
    products = t.get("products") or {}
    rows = [
        {
            "observation_date": str(r["effective"]),
            "country": t["country"],
            "fuel_product": r["product"],
            "price_local": float(r["price_local"]),
            "currency": t["currency"],
            "unit": _UNITS.get(
                (products.get(r["product"]) or {}).get("unit", "liter"), "L"
            ),
            "source_key": t["source_key"],
            "city": None if r["locality"] == "national" else r["locality"],
            "station_type": "national" if r["locality"] == "national" else "city",
        }
        for r in t.get("levels") or []
        if r.get("price_local") is not None
        and r.get("confidence") != "baja"
        and pd.Timestamp(r["effective"]).date() > cutoff
    ]
    return pd.DataFrame(rows) if rows else None


__all__ = ["read_manual_levels", "table_path"]
