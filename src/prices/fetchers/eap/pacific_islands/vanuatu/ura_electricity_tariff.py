"""Vanuatu Utilities Regulatory Authority (URA) -- regulated electricity tariff.

The URA "regulated services" page (Itemid=180&id=14) renders a single static
HTML table covering BOTH electricity and water rates, grouped by a rowspan
header cell ("ELECTRICITY" / "WATER") in the first column. This fetcher reads
only the electricity block; ``ura_water_tariff.py`` is the sibling fetcher for
the water block on the same page (two YAMLs -- narrow COICOP codes, 04.5.1
vs 04.4.1 -- per the onboarding skill's "two shapes on one site" rule).

Prices are the regulator's own per-unit RATE (Vatu/kWh), not a shelf price for
a discrete purchased item -- URA publishes these to two decimal places (e.g.
60.25 VUV/kWh) even though VUV itself has no minor unit. This is the source's
own published figure (confirmed by direct fetch, not a parsing artifact): a
customer's actual bill is `rate * kWh consumed`, rounded to the nearest vatu
at billing time, but the regulated RATE itself is quoted with two decimals.
Flagged loudly here and in the YAML notes per onboarding rule about
deviations from the country's currency norm.

vnso.gov.vu-class TLS quirk applies here too -- URA's `*.gov.vu` cert chain
resolves fine in curl/macOS but not python's certifi-only context; `verify=False`
is required (see known_blockers.md "NSO portal SSL certificate failures").
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
_SOURCE_KEY = "vu_ura_electricity_tariff"
_COICOP = "04.5.1"
_UNIT = "kWh"
_IDENT = ["source_key", "effective_from", "item_name"]

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_DATE_RE = re.compile(r"(\d{1,2}\s+(?:" + _MONTHS + r")\s+\d{4})")
_MONTH_YEAR_RE = re.compile(r"((?:" + _MONTHS + r")\s+\d{4})")


def _parse_effective_date(raw: str) -> date | None:
    """Best-effort date extraction from a messy 'Effective As Of' cell.

    Handles a clean 'DD Month YYYY', a trailing '*' footnote marker, a bare
    'Month YYYY' (day defaults to 1st), and prose like 'Price- is effective
    as of 25 July 2015. Pending Determination new tariff' (Bukura Water
    Supply) by regex-searching for a date substring rather than requiring an
    exact match.
    """
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

        if current_section != "ELECTRICITY":
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


def fetch_vu_ura_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30, verify=False)
    resp.raise_for_status()

    parsed = _parse_rows(resp.text)
    if not parsed:
        logger.warning("[%s] No electricity rows found at %s", _SOURCE_KEY, _URL)
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
            "item_name": f"Electricity tariff – {item['utility']}",
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
