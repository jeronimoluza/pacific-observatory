"""MCI (Hamrah-e Aval, mci.ir) -- Iran's incumbent mobile operator, prepaid
call/SMS/data tariffs and administrative service fees.

Verified live 2026-09-28: https://mci.ir/prepaid-tariff is a plain
server-rendered HTML page (no JS, no WAF) carrying four
``<table class="dpco-mci-table">`` blocks -- per-minute call rates,
per-page SMS rates, one-time administrative service fees (SIM
replacement, number change, porting, ...), and per-KB data rates for the
default (non-bundle) credit-SIM tariff. All values are already
Rial-denominated in the page's own header text ("... (ریال)") -- unlike
the retailer WooCommerce stores onboarded alongside this source, MCI does
NOT quote in Toman, so no PRICE_MULTIPLIER/unit conversion is applied
here.

``pandas.read_html`` parses all four tables cleanly, including the
rowspan/colspan cells (SMS table's service-type column, admin-fee table's
multi-line values) -- confirmed against the raw HTML dump saved during
probing. Positional column access (``iloc``) is used throughout rather
than named columns, because the header text round-trips awkwardly through
pandas' column-naming for the colspan'd SMS table.

Whole catalog is telecommunication services -> coicop_code "08.3.0"
hardcoded for every row (coicop_classification: source_curated).

Test run (cutoff=2024-01-01): 4 tables read, ~26 candidate rows before
the numeric-parse filter (one admin-fee row -- itemized call-log printing
-- carries a two-part price text ("برگ اول ... و مازاد بر آن ...") that
does not reduce to one number and is dropped per the "drop rows whose
coicop-eligible price can't be resolved" rule, logged as a warning, not
silently swallowed).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from io import StringIO
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_URL = "https://mci.ir/prepaid-tariff"
_COUNTRY = "Iran, Islamic Rep."
_SOURCE_KEY = "ir_mci_tariff"
_CURRENCY = "IRR"
_COICOP = "08.3.0"
_IDENT = ["source_key", "item_name", "unit"]

_NUM_RE = re.compile(r"[\d,]+\.?\d*")


def _first_number(text) -> float | None:
    if text is None:
        return None
    m = _NUM_RE.search(str(text).replace("‌", "").replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _rows_from_tables(tables: list[pd.DataFrame]) -> list[dict]:
    rows: list[dict] = []

    if len(tables) > 0:
        # Per-minute call rates: col0=row#, col1=call type, col2=rate (IRR)
        for _, r in tables[0].iterrows():
            label = str(r.iloc[1]).strip()
            price = _first_number(r.iloc[2])
            if not label or price is None:
                continue
            rows.append(
                {
                    "item_name": f"MCI prepaid call: {label}",
                    "price_local": price,
                    "unit": "per_minute",
                }
            )

    if len(tables) > 1:
        # SMS rates: col0=service type, col1=subtype (Farsi/English), col2=rate (IRR)
        for _, r in tables[1].iterrows():
            service = str(r.iloc[0]).strip()
            subtype = str(r.iloc[1]).strip()
            price = _first_number(r.iloc[2])
            if not service or price is None:
                continue
            rows.append(
                {
                    "item_name": f"MCI {service} ({subtype})",
                    "price_local": price,
                    "unit": "per_message",
                }
            )

    if len(tables) > 2:
        # Administrative service fees: col0=service name, col2=final amount incl. VAT (IRR)
        for _, r in tables[2].iterrows():
            service = str(r.iloc[0]).strip()
            price = _first_number(r.iloc[2])
            if not service or price is None:
                logger.warning(
                    "[%s] Dropping admin-fee row with unparseable price: %r",
                    _SOURCE_KEY,
                    service,
                )
                continue
            rows.append(
                {
                    "item_name": f"MCI service fee: {service}",
                    "price_local": price,
                    "unit": "one_time",
                }
            )

    if len(tables) > 3:
        # Data rate: col0=SIM type, col1=rate per KB, general sites (IRR)
        for _, r in tables[3].iterrows():
            sim_type = str(r.iloc[0]).strip()
            price = _first_number(r.iloc[1])
            if not sim_type or price is None:
                continue
            rows.append(
                {
                    "item_name": f"MCI data ({sim_type}, standard sites)",
                    "price_local": price,
                    "unit": "per_kb",
                }
            )

    return rows


def fetch_ir_mci_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    try:
        resp = session.get(_URL, timeout=30)
    except requests.RequestException as exc:
        logger.warning("[%s] Request failed for %s: %s", _SOURCE_KEY, _URL, exc)
        return None
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    try:
        tables = pd.read_html(StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] No tables parsed: %s", _SOURCE_KEY, exc)
        return None

    parsed = _rows_from_tables(tables)
    if not parsed:
        logger.warning("[%s] No tariff rows parsed", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": None,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
