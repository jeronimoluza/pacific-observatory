"""b-material.mn building-material and hardware listings."""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://b-material.mn/"
_COUNTRY = "Mongolia"
_SUBNATIONAL_AREA = "Ulaanbaatar"
_SOURCE_KEY = "mn_b_material_mn"
_CURRENCY = "MNT"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_PRICE_RE = re.compile(r"^(?P<name>.+?)\s+(?P<price>[0-9][0-9’']*)$")


def _clean(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _parse_price(raw: str) -> float:
    return float(raw.replace("’", "").replace("'", ""))


def fetch_mn_b_material_mn(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href^="/product/"]'):
        text = _clean(anchor.get_text(" ", strip=True))
        match = _PRICE_RE.match(text)
        if not match:
            continue
        item_name = _clean(match.group("name"))
        price = _parse_price(match.group("price"))
        source_url = urljoin(_URL, anchor["href"])
        if not item_name or price <= 0 or source_url in seen:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL_AREA,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "item",
            "source_url": source_url,
            "notes": "homepage building-material and tool product card",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
        seen.add(source_url)

    logger.info("[%s] parsed %d building-material rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
