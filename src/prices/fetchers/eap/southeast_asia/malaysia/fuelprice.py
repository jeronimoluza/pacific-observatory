"""Malaysia data.gov.my weekly petroleum and diesel retail prices."""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://storage.data.gov.my/commodities/fuelprice.csv"
_COUNTRY = "Malaysia"
_CURRENCY = "MYR"
_SOURCE_KEY = "my_fuelprice"
_SOURCE_URL = "https://data.gov.my/data-catalogue/fuelprice"
_COICOP = "07.2.2"
_UNIT = "litre"
_IDENT = ["source_key", "observation_date", "item_name"]

_SERIES = {
    "ron95": ("RON95 petrol", None),
    "ron97": ("RON97 petrol", None),
    "diesel": ("Diesel", "Peninsular Malaysia"),
    "diesel_eastmsia": ("Diesel", "East Malaysia"),
    "ron95_budi95": ("RON95 petrol, BUDI 95 subsidy", None),
    "ron95_skps": ("RON95 petrol, SKPS commercial subsidy", None),
    "diesel_skds": ("Diesel, SKDS subsidy", None),
    "diesel_budi": ("Diesel, BUDI subsidy", None),
}


def fetch_my_fuelprice(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df = df[df["series_type"].eq("level")].copy()
    df["observation_date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df[df["observation_date"].notna() & (df["observation_date"] > cutoff)]

    rows: list[dict] = []
    ts = get_scrape_ts()
    for _, src in df.iterrows():
        obs_date = src["observation_date"]
        for column, (label, subnational_area) in _SERIES.items():
            price = pd.to_numeric(src.get(column), errors="coerce")
            if pd.isna(price) or float(price) <= 0:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "weekly_effective",
                "country": _COUNTRY,
                "subnational_area": subnational_area,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": label,
                "price_local": round(float(price), 4),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _SOURCE_URL,
                "notes": "Ministry of Finance weekly retail fuel price via data.gov.my",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info("[%s] %d rows after cutoff %s", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
