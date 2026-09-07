"""Thailand Ministry of Commerce public agricultural commodity price cards."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.moc.go.th/en/page/item/index/id/1"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_moc_agri_prices"
_IDENT = ["source_key", "observation_date", "item_name"]

_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _as_price(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        value = float(raw.strip().replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_thai_date(raw: str | None) -> date | None:
    if not raw:
        return None
    m = _DATE_RE.search(raw)
    if not m:
        return None
    day, month, year = (int(part) for part in m.groups())
    if year > 2400:
        year -= 543
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _unit(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    if text == "บาท/กก.":
        return "kg"
    if text == "บาท/100 กก.":
        return "100 kg"
    if text == "บาท/หวี":
        return "bunch"
    if text == "บาท/ขวด":
        return "bottle"
    if text == "บาท/ฟอง":
        return "egg"
    return text.replace("บาท/", "").strip() or text


def fetch_th_moc_agri_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict] = []
    ts = get_scrape_ts()
    for card in soup.select(".infocard"):
        name_el = card.select_one("h3")
        price_el = card.select_one(".price")
        unit_el = card.select_one(".unit")
        date_el = card.select_one(".date")
        if not (name_el and price_el and date_el):
            continue

        obs_date = _parse_thai_date(date_el.get_text(" ", strip=True))
        price = _as_price(price_el.get_text(" ", strip=True))
        name = name_el.get_text(" ", strip=True)
        if not (obs_date and price and name) or obs_date <= cutoff:
            continue

        unit = _unit(unit_el.get_text(" ", strip=True) if unit_el else None)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": name[:500],
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "notes": f"Ministry of Commerce commodity price card; raw unit={unit_el.get_text(' ', strip=True) if unit_el else ''}; raw date={date_el.get_text(' ', strip=True)}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows after cutoff %s", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
