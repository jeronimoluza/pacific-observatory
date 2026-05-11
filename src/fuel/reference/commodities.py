"""Commodity price series loader for the publish stage.

Reads observations from ``data/fuel/_global/investing_daily/observations.csv``.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_GAL_PER_BBL = 42.0


def load_commodity_series(
    data_dir: Path,
    history_years: int = 3,
) -> dict[str, dict]:
    """Load commodity price observations and return per-product series.

    Returns ``{product_name: {"points": [{"x": date_str, "y": price}], "unit": str, "currency": str}}``.
    """
    obs_path = data_dir / "_global" / "investing_daily" / "observations.csv"
    if not obs_path.exists():
        logger.warning("Commodity observations not found: %s", obs_path)
        return {}

    df = pd.read_csv(obs_path, low_memory=False)
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = df.dropna(subset=["observation_date", "price_local"])
    df["price_local"] = pd.to_numeric(df["price_local"], errors="coerce")
    df = df[df["price_local"] > 0].copy()

    cutoff = (date.today() - timedelta(days=365 * history_years)).strftime("%Y-%m-%d")

    series: dict[str, dict] = {}
    for prod in df["fuel_product"].dropna().unique():
        rows = df[df["fuel_product"] == prod].sort_values("observation_date")
        unit = rows["unit"].iloc[0] if "unit" in rows.columns else ""
        currency = rows["currency"].iloc[0] if "currency" in rows.columns else ""
        unit_norm = unit
        unit_factor = 1.0
        if unit == "gal":
            unit_norm = "bbl"
            unit_factor = _GAL_PER_BBL
        pts = [
            {
                "x": r["observation_date"].strftime("%Y-%m-%d"),
                "y": round(float(r["price_local"]) * unit_factor, 4),
            }
            for _, r in rows.iterrows()
            if pd.notna(r["price_local"])
        ]
        pts = [p for p in pts if p["x"] >= cutoff]
        if pts:
            series[prod] = {"points": pts, "unit": unit_norm, "currency": currency}

    logger.info("Loaded %d commodity series from %s", len(series), obs_path)
    return series
