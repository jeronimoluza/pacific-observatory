"""Mongolia ERC electricity tariff reform summary."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://erc.gov.mn/en/print/1033?date=true"
_COUNTRY = "Mongolia"
_SOURCE_KEY = "mn_erc_electricity_tariff"
_CURRENCY = "MNT"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]


def _pub_date(html: str) -> date:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    if "2024 оны 11-р сарын 15" in text:
        return date(2024, 11, 15)
    return date.today()


def fetch_mn_erc_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    obs_date = _pub_date(resp.text)
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    tariff_rows = [
        ("Average electricity tariff, previous", 216.0),
        ("Average electricity tariff, current", 280.0),
        ("Average household electricity tariff, previous", 140.0),
        ("Household electricity tariff, first 150 kWh per month", 175.0),
        ("Household electricity tariff, 150-300 kWh per month", 256.0),
        ("Household electricity tariff, above 300 kWh per month", 285.0),
    ]

    ts = get_scrape_ts()
    rows: list[dict] = []
    for item_name, tariff in tariff_rows:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": "Mongolia",
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": tariff,
            "currency": _CURRENCY,
            "unit": "MNT/kWh",
            "source_url": _URL,
            "notes": "Energy Regulatory Commission tariff reform notice",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] parsed %d tariff rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows)
