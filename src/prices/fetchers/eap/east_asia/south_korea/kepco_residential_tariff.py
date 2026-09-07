"""KEPCO residential electricity bill table by monthly kWh consumed."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URLS = [
    "https://home.kepco.co.kr/kepco/indi/foreign/en/html/F/B/ENFBHP002_pop01.html",
    "https://home.kepco.co.kr/kepco/indi/foreign/en/html/F/B/ENFBHP002_pop02.html",
    "https://home.kepco.co.kr/kepco/indi/foreign/en/html/F/B/ENFBHP002_pop03.html",
]
_COUNTRY = "Korea, Rep."
_CURRENCY = "KRW"
_SOURCE_KEY = "kr_kepco_residential_tariff"
_COICOP = "04.5.1"
_UNIT = "monthly bill"
_IDENT = ["source_key", "observation_date", "kwh"]


def _parse_pairs(html: str) -> list[tuple[int, float]]:
    soup = BeautifulSoup(html, "html.parser")
    pairs: list[tuple[int, float]] = []
    for tr in soup.select("table tr"):
        values = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        for i in range(0, len(values) - 1, 2):
            raw_kwh = values[i].replace(",", "")
            raw_rate = values[i + 1].replace(",", "")
            if not raw_kwh.isdigit() or not raw_rate.isdigit():
                continue
            pairs.append((int(raw_kwh), float(raw_rate)))
    return pairs


def fetch_kr_kepco_residential_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[int] = set()
    for url in _URLS:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        for kwh, bill in _parse_pairs(resp.text):
            if kwh in seen or not 0 < bill < 10_000_000:
                continue
            seen.add(kwh)
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"Residential electricity bill at {kwh} kWh monthly use",
                "price_local": bill,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": url,
                "notes": "KEPCO English residential electric rates table by amount consumed",
                "scrape_ts": ts,
                "kwh": kwh,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            row.pop("kwh")
            rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
