"""MTN Congo -- prepaid mobile-internet data-bundle tariff, Republic of the
Congo.

Scrapes the server-rendered "Forfaits Internet classiques" page at mtn.cg.
Six sections, each a <table> of "Volume en Mo" / "Prix" pairs, preceded by a
heading naming its validity window: 1 jour, 7 jours, 30 jours, plus three
named offers (NUIT, FTT, Résidentielles). No JS, no WAF -- verified live
2026-09-28 with a plain `requests` session (get_session()).

Prices are lump-sum package prices in FCFA ("130F", "1 600F"), not a
per-unit rate, so unit="forfait" and the data volume is folded into
item_name. One row, "Illimité" (unlimited), has no numeric volume.

COICOP: 08.3.0 (telephone, telefax and internet access services).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://www.mtn.cg/particuliers/forfaits/forfaits-internet-classiques/"
_COUNTRY = "Congo, Rep."
_CURRENCY = "XAF"
_SOURCE_KEY = "cog_mtn_internet_tariff"
_COICOP_CODE = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_fcfa_price(text: str) -> float | None:
    """'130F' -> 130.0 ; '1 600F' -> 1600.0."""
    cleaned = text.replace("\xa0", "").replace(" ", "").strip()
    cleaned = re.sub(r"[Ff]$", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_tariff_rows(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    for table in soup.find_all("table"):
        heading = table.find_previous(["h2", "h3", "strong", "span"])
        section = heading.get_text(" ", strip=True) if heading else "Forfaits Internet"
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) != 2:
                continue
            volume_text, price_text = cells
            if volume_text.strip().lower().startswith("volume"):
                continue  # header row
            price_local = _parse_fcfa_price(price_text)
            if price_local is None:
                continue
            item_name = f"MTN Congo Internet, {section}, {volume_text}"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "forfait",
                "source_url": _TARIFF_URL,
                "notes": f"Prepaid data bundle, {section}",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_cog_mtn_internet_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _TARIFF_URL
        )
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = _extract_tariff_rows(soup, obs_date)
    if not rows:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _TARIFF_URL)
        return None

    return pd.DataFrame(rows)
