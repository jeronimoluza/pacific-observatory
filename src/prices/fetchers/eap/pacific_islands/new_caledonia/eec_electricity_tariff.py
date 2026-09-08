"""Electricité et Eau de Calédonie (EEC) — regulated electricity tariff, New Caledonia.

EEC's public tariff page (a single static WordPress page) publishes the
regulated retail electricity schedule set by the government of New
Caledonia, stamped "Grille tarifaire en vigueur du 1er octobre 2025". The
page holds nine HTML tables in total; this fetcher takes the two
unambiguous, per-consumer tables and skips the rest:

- "Prix unitaire (en FCFP)" — per-kWh energy rate by usage category
  (Domestic <=3.3kVA / Domestic >3.3kVA / Professional).
- "Redevance comptage (FCFP)" — fixed monthly metering fee by meter/breaker
  type (5 rows).

Skipped on purpose: the photovoltaic feed-in tariff table ("Tarif d'achat",
a rate EEC PAYS OUT to consumers with solar panels, not a price consumers
pay — out of scope for a consumer price basket) and several
calibre/PRIME FIXE tables whose merged multi-row headers make the
category boundary ambiguous without risking a misread.

**Decimal-comma trap**: `pandas.read_html` silently mangles the source's
comma-decimal figures ("37,91" -> parsed as the integer 3791) because it
has no locale awareness. This fetcher parses the raw table cells with
BeautifulSoup and does the comma-to-dot substitution itself; RAW HTML
MUST be read directly rather than through `pd.read_html` for any table
on this page.

Verified live 2026-09-06: 8 rows (3 unit-price + 5 metering-fee), dated
2025-10-01 per the page's own "en vigueur du" stamp.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://eec.nc/institutionnel/eec-2/tarifs-eec-nouvelle-caledonie"
_COUNTRY = "New Caledonia"
_CURRENCY = "XPF"
_SOURCE_KEY = "nc_eec_electricity_tariff"
_COICOP = "04.5.1.0"

_IDENT = ["source_key", "effective_from", "item_name"]

_EFFECTIVE_RE = re.compile(
    r"en vigueur du\s+1\s*er\s+([A-Za-zéû]+)\s+(\d{4})", re.I
)

_MONTHS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12,
}


def _parse_fr_number(text: str) -> float | None:
    """'37,91' -> 37.91; '3 182' / '3\\xa0182' -> 3182."""
    cleaned = text.replace("\xa0", " ").strip()
    cleaned = re.sub(r"(?<=\d)\s(?=\d)", "", cleaned)  # drop thousands spaces
    cleaned = cleaned.replace(",", ".")
    m = re.search(r"[\d.]+", cleaned)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _table_rows(table) -> list[list[str]]:
    return [
        [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        for tr in table.find_all("tr")
    ]


def fetch_nc_eec_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text(" ", strip=True)

    m = _EFFECTIVE_RE.search(text)
    if not m:
        logger.warning("[%s] Could not parse effective date", _SOURCE_KEY)
        return None
    month_name, year_s = m.groups()
    month_num = _MONTHS_FR.get(month_name.lower())
    if month_num is None:
        logger.warning("[%s] Unrecognized French month %r", _SOURCE_KEY, month_name)
        return None
    effective_from = date(int(year_s), month_num, 1)

    if effective_from <= cutoff:
        logger.info("[%s] No new data since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    tables = soup.find_all("table")
    parsed_rows: list[dict] = []

    unit_price_table = next(
        (t for t in tables if "Prix unitaire" in t.get_text()), None
    )
    if unit_price_table is not None:
        for row in _table_rows(unit_price_table)[1:]:
            if len(row) < 2:
                continue
            label, price_text = row[0], row[1]
            price = _parse_fr_number(price_text)
            if price is None:
                continue
            parsed_rows.append(
                {
                    "item_name": f"Electricity tariff – Unit price ({label})",
                    "price_local": price,
                    "unit": "kWh",
                }
            )
    else:
        logger.warning("[%s] Could not find the unit-price table", _SOURCE_KEY)

    metering_table = next(
        (t for t in tables if "Redevance comptage" in t.get_text()), None
    )
    if metering_table is not None:
        for row in _table_rows(metering_table)[1:]:
            if len(row) < 2:
                continue
            label, price_text = row[0], row[1]
            price = _parse_fr_number(price_text)
            if price is None:
                continue
            parsed_rows.append(
                {
                    "item_name": f"Electricity tariff – Metering fee ({label})",
                    "price_local": price,
                    "unit": "month",
                }
            )
    else:
        logger.warning("[%s] Could not find the metering-fee table", _SOURCE_KEY)

    rows = []
    for item in parsed_rows:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": _TARIFF_URL,
            "notes": "EEC-published regulated electricity tariff (government-set).",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
