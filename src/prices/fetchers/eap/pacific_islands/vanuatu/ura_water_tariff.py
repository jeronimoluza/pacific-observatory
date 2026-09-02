"""Vanuatu Utilities Regulatory Authority (URA) -- regulated water tariff.

Sibling fetcher to ``ura_electricity_tariff.py`` -- same page, same table,
the WATER rowspan block instead of ELECTRICITY. See that module's docstring
for the rowspan-parsing rationale, the TLS `verify=False` requirement, and
the note on why these regulator RATES carry 2dp precision despite VUV having
no minor unit.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import urllib3
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_URL = (
    "https://ura.gov.vu/index.php?Itemid=180&id=14&lang=en&option=com_content"
    "&view=article"
)
_COUNTRY = "Vanuatu"
_CURRENCY = "VUV"
_SOURCE_KEY = "vu_ura_water_tariff"
_COICOP = "04.4.1"
_UNIT = "m3"
_IDENT = ["source_key", "effective_from", "item_name"]

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_DATE_RE = re.compile(r"(\d{1,2}\s+(?:" + _MONTHS + r")\s+\d{4})")
_MONTH_YEAR_RE = re.compile(r"((?:" + _MONTHS + r")\s+\d{4})")


def _parse_effective_date(raw: str) -> date | None:
    text = raw.replace("*", "").strip()
    m = _DATE_RE.search(text)
    if m:
        return pd.to_datetime(m.group(1), format="%d %B %Y").date()
    m = _MONTH_YEAR_RE.search(text)
    if m:
        return pd.to_datetime("1 " + m.group(1), format="%d %B %Y").date()
    return None


def _parse_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.table-bordered") or soup.find("table")
    if table is None:
        return []

    current_section: str | None = None
    out: list[dict] = []

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        if texts[0] in ("Regulated Service", "Electricity Utility"):
            continue  # header row

        if len(cells) == 5:
            current_section = texts[0].upper()
            utility, unit, price, effective = texts[1], texts[2], texts[3], texts[4]
        elif len(cells) == 4:
            utility, unit, price, effective = texts[0], texts[1], texts[2], texts[3]
        else:
            continue

        if current_section != "WATER":
            continue

        out.append(
            {
                "utility": utility,
                "unit_text": unit,
                "price_text": price,
                "effective_text": effective,
            }
        )

    return out


def fetch_vu_ura_water_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30, verify=False)
    resp.raise_for_status()

    parsed = _parse_rows(resp.text)
    if not parsed:
        logger.warning("[%s] No water rows found at %s", _SOURCE_KEY, _URL)
        return None

    rows = []
    for item in parsed:
        effective_from = _parse_effective_date(item["effective_text"])
        if effective_from is None:
            logger.warning(
                "[%s] Could not parse effective date %r for %r -- dropping row",
                _SOURCE_KEY,
                item["effective_text"],
                item["utility"],
            )
            continue
        if effective_from <= cutoff:
            continue
        try:
            price_local = float(item["price_text"].replace(",", ""))
        except ValueError:
            logger.warning(
                "[%s] Could not parse price %r for %r -- dropping row",
                _SOURCE_KEY,
                item["price_text"],
                item["utility"],
            )
            continue
        if price_local <= 0:
            continue

        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"Water tariff – {item['utility']}",
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _URL,
            "notes": (
                "URA-published regulated rate, quoted to 2dp by the source "
                "despite VUV having no minor unit; not a parse artifact."
            ),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
