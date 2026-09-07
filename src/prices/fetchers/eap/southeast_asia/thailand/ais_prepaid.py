"""AIS One-2-Call prepaid package tariffs."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.ais.th/consumers/package/prepaid/plan/call-internet"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_ais_prepaid"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]

_PLANS = [
    ("5G Max Speed weekly package", 129, "per week; 100GB at 4 Mbps then 128 Kbps"),
    ("5G Max Speed quota weekly package", 99, "per week; 1GB/day then 1 Mbps"),
    ("Freedom Unlimited weekly package", 99, "per week; unlimited 2 Mbps"),
    ("iSmart monthly package, 500 MB", 299, "per month; 100 call minutes"),
    ("iSmart monthly package, 750 MB", 399, "per month; 150 call minutes"),
    ("iSmart monthly package, 1.5 GB", 599, "per month; 300 call minutes"),
    ("iSmart monthly package, 2 GB", 799, "per month; 400 call minutes"),
    ("iSmart monthly package, 3 GB", 999, "per month; 500 call minutes"),
]


def fetch_th_ais_prepaid(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "html.parser").get_text("\n", strip=True)

    rows: list[dict] = []
    ts = get_scrape_ts()
    for item_name, price, notes in _PLANS:
        if f"{price} บาท" not in text:
            logger.warning(
                "[%s] expected price marker missing: %s", _SOURCE_KEY, item_name
            )
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": float(price),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": notes,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
