"""Smart Philippines prepaid daily data add-on tariffs."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Philippines"
_CURRENCY = "PHP"
_SOURCE_KEY = "ph_smart_daily_data"
_COICOP = "08.3.0"
_UNIT = "package"
_IDENT = ["source_key", "observation_date", "item_name"]
_URL = "https://store.smart.com.ph/promos-and-add-ons/smart-prepaid/daily-data"

_PRICE_RE = re.compile(r"^₱\s*([0-9][0-9,.]*)$")


def _lines(html: str) -> list[str]:
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _price(raw: str) -> float | None:
    m = _PRICE_RE.match(raw)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _extract_packages(lines: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for i, line in enumerate(lines):
        if line.lower() != "only" or i == 0 or i + 1 >= len(lines):
            continue
        price = _price(lines[i + 1])
        if price is None:
            continue
        item_name = lines[i - 1]
        nearby = [
            part
            for part in lines[max(0, i - 2) : min(len(lines), i + 3)]
            if part != "This item cannot be compared to the other selected item"
        ]
        notes = "; ".join(nearby)
        rows.append((item_name, price, notes))
    return rows


def fetch_ph_smart_daily_data(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    resp = get_session().get(_URL, timeout=45)
    resp.raise_for_status()

    rows: list[dict] = []
    seen: set[str] = set()
    ts = get_scrape_ts()
    for item_name, price, notes in _extract_packages(_lines(resp.text)):
        key = item_name.lower()
        if key in seen:
            continue
        seen.add(key)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name[:500],
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _URL,
            "notes": notes[:500],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
