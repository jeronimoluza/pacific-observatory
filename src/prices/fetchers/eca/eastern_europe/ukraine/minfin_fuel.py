"""Minfin Index — Ukraine retail fuel prices by oblast.

Scrapes the daily-snapshot table at
``https://index.minfin.com.ua/ua/markets/fuel/reg/`` — 23 oblasts ×
5 fuel grades (A-95+, A-95, A-92, ДП/diesel, Газ/auto-LPG) = up to
115 daily PriceObservations per run.

The page renders one snapshot per day. Source values are in kopiykas
(UAH cents) per litre; emitted as UAH/L. Oblast labels are kept in
Ukrainian and folded into ``item_name`` since PRICE_COLUMNS has no
subnational slot.

All five fuels are COICOP 07.2.2 — auto-LPG retailed at AZS is a
vehicle fuel, not a domestic-heating fuel.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://index.minfin.com.ua/ua/markets/fuel/reg/"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_minfin_fuel"
_COICOP = "07.2.2"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name"]

_FUEL_LABELS = {
    "А 95+": "A-95 premium",
    "А 95": "A-95",
    "А 92": "A-92",
    "ДП": "Diesel",
    "Газ": "Auto LPG",
}


def fetch_ua_minfin_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text))
    if not tables:
        logger.warning("No tables parsed from %s", _URL)
        return None
    df = tables[0]
    df.columns = [str(c).replace("\xa0", " ").strip() for c in df.columns]
    if df.shape[1] < 6 or "Область" not in df.columns:
        logger.warning("Unexpected table shape from %s: %s", _URL, df.shape)
        return None

    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        logger.info("obs_date %s <= cutoff %s — no new rows", obs_date, cutoff)
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for _, src in df.iterrows():
        oblast = str(src["Область"]).strip()
        if not oblast or oblast.lower() == "nan":
            continue
        for col_label, fuel_name in _FUEL_LABELS.items():
            if col_label not in df.columns:
                continue
            raw = src[col_label]
            if pd.isna(raw):
                continue
            try:
                kopiykas = float(raw)
            except (TypeError, ValueError):
                continue
            if kopiykas <= 0:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"{fuel_name} avg pump price, {oblast} oblast",
                "price_local": round(kopiykas / 100.0, 2),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _URL,
                "notes": "weighted oblast average across operators",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("No fuel rows extracted from %s", _URL)
        return None
    return pd.DataFrame(rows)
