"""Chuuk Public Utility Corporation (CPUC) -- electricity + water tariff.

cpuc.fm publishes its "Current Tariffs and Change Process" page
(``/cpucs-current-tariffs-and-tariff-change-process``) as several
server-rendered HTML ``<table>``s under plain-text headings. Tier 1A, plain
``requests`` -- no WAF, no JS.

Three tables are extracted, keyed off the heading text that precedes them
(same anchoring approach as ``puc_tariff.py``):

- **"Fuel Price Index Adjustment"** -- the live, fuel-cost-adjusted
  electricity rate notice CPUC re-issues roughly monthly. Columns give both
  Weno and Tonoas rates per customer category ("From Current Rate" / "To
  New Rate"); we take the "To New Rate" column, i.e. the rate now in force
  after this notice. A second, separate "Table 1 -- Electricity Supply
  Tariff Base" table further down the page carries a stale 2021/09/15
  snapshot and is intentionally NOT read.
- **"Water Supply Tariffs"** -- two tiered-usage tables in sequence
  (Residential, then Commercial & Government), each with a minimum charge.

A fourth table under "Sewerage Tariffs" ("Table 4 -- Proposed Sewerage
Tariff Price Path") is explicitly labelled "Proposed" (a 3-year phase-in of
percentages, not an in-force absolute price) and is deliberately NOT
extracted -- it is not yet a real, chargeable rate.

No single effective-date reliably covers every table on the page (the
electricity notice states one, e.g. "Prices effective 22nd July 2026", but
the water tables do not), so -- same as ``puc_tariff.py`` and
``fsmtc_tariff.py`` -- this is modelled as a daily period_kind=snapshot at
scrape time rather than trying to parse a per-row effective date.

Currency is USD (FSM's actual currency, no FX conversion needed).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_cpuc_tariff"
_STATE = "Chuuk"
_URL = "https://www.cpuc.fm/cpucs-current-tariffs-and-tariff-change-process"
_IDENT = ["source_key", "observation_date", "item_name"]

_ELECTRICITY_COICOP = "04.5.1"
_WATER_COICOP = "04.4.1"

_ELECTRICITY_CATEGORIES = ("Residential", "Commercial", "Government")


def _price(text: str) -> float | None:
    m = re.search(r"[\d,.]+", text.replace(",", ""))
    if not m:
        return None
    try:
        val = float(m.group(0))
    except ValueError:
        return None
    return val if val > 0 else None


def _tables_after_heading(soup: BeautifulSoup, heading_text: str, n: int) -> list:
    heading = soup.find(
        lambda tag: tag.name in ("h1", "h2", "h3", "h4", "h5")
        and tag.get_text(strip=True) == heading_text
    )
    if heading is None:
        return []
    tables = []
    node = heading
    for _ in range(n):
        node = node.find_next("table")
        if node is None:
            break
        tables.append(node)
    return tables


def _parse_electricity(table) -> list[dict]:
    out = []
    rows = table.find_all("tr")
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        category = cells[0].get_text(" ", strip=True)
        if category not in _ELECTRICITY_CATEGORIES:
            continue
        weno = _price(cells[2].get_text(" ", strip=True))
        tonoas = _price(cells[4].get_text(" ", strip=True))
        if weno is not None:
            out.append(
                {
                    "item_name": f"Electricity -- {category} (Weno)",
                    "price_local": weno,
                    "unit": "USD/kWh",
                    "coicop_code": _ELECTRICITY_COICOP,
                }
            )
        if tonoas is not None:
            out.append(
                {
                    "item_name": f"Electricity -- {category} (Tonoas)",
                    "price_local": tonoas,
                    "unit": "USD/kWh",
                    "coicop_code": _ELECTRICITY_COICOP,
                }
            )
    return out


def _parse_water(table, label: str) -> list[dict]:
    out = []
    rows = table.find_all("tr")
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue
        usage = cells[0].get_text(" ", strip=True)
        price_text = cells[1].get_text(" ", strip=True)
        price = _price(price_text)
        if price is None or not usage:
            continue
        unit = "USD/month" if "Minimum" in usage else "USD/1000gal"
        out.append(
            {
                "item_name": f"Water {label} -- {usage}",
                "price_local": price,
                "unit": unit,
                "coicop_code": _WATER_COICOP,
            }
        )
    return out


def fetch_fm_cpuc_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    items: list[dict] = []

    electricity_tables = _tables_after_heading(soup, "Fuel Price Index Adjustment", 1)
    if electricity_tables:
        items += _parse_electricity(electricity_tables[0])
    else:
        logger.warning("[%s] electricity rate table not found", _SOURCE_KEY)

    water_tables = _tables_after_heading(soup, "Water Supply Tariffs", 2)
    if len(water_tables) == 2:
        items += _parse_water(water_tables[0], "Residential")
        items += _parse_water(water_tables[1], "Commercial & Government")
    else:
        logger.warning(
            "[%s] expected 2 water tariff tables, found %d",
            _SOURCE_KEY,
            len(water_tables),
        )

    if not items:
        logger.warning("[%s] no tariff rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in items:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": _STATE,
            "source_key": _SOURCE_KEY,
            "coicop_code": item["coicop_code"],
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "source_url": _URL,
            "notes": None,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
