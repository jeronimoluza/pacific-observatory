"""Vodafone Fiji -- prepay call/SMS/mobile-internet per-unit rates.

Vodafone Fiji publishes its prepay rate card as two static server-rendered
HTML tables on one page (no JS, no API, no anti-bot -- plain ``requests``
works): "Standard Prepay Sims" and "Bula Packs & Tourist Sims", each a
2-column (Transaction Description, Rate) table covering local on-/off-net
voice calls, call forwarding, customer-care calls, SMS, MMS, and mobile
internet (per-MB).

No effective-date is published anywhere on the page (unlike a regulator
tariff order) -- this is a "current rate" page Vodafone edits in place.
Modelled as a daily ``period_kind: snapshot`` at scrape time, same pattern
as FSM's fsmtc_tariff.py -- the fetcher re-reads the live page every run, so
a rate change surfaces as a new observation_date row with a different
price, no hardcoded table to go stale.

One row ("Calls to Vodafone Customer Care (123)") packs two rates (Peak /
Off-Peak) into a single cell separated by " | " -- split into two line
items rather than dropped or averaged.

Currency: FJD (Fiji dollar, matches countries.yaml). Verified live
2026-09-06: 29 tariff line items across both tables.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://vodafone.com.fj/personal/price-plans/rates-price-plan/prepay-call-rates"
_COUNTRY = "Fiji"
_CURRENCY = "FJD"
_SOURCE_KEY = "fj_vodafone_prepay_rates"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"\$\s*([\d,.]+)\s*(per\s+\S+)", re.I)


def _split_rate_cell(price_text: str) -> list[tuple[str, float, str]]:
    """Parse one rate cell into (label_suffix, price, unit) tuples.

    Handles the common single-rate case ("$0.27 per unit") and the
    compound "Peak $0.55 per minute | Off-Peak $0.36 per minute" case.
    """
    out = []
    for segment in price_text.split("|"):
        segment = segment.strip()
        label_prefix = ""
        m_label = re.match(r"^(Peak|Off-Peak)\b", segment, re.I)
        if m_label:
            label_prefix = f" ({m_label.group(1)})"
        m = _PRICE_RE.search(segment)
        if not m:
            continue
        try:
            price = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        unit = m.group(2).strip()
        out.append((label_prefix, price, unit))
    return out


def _rows_from_table(table, section: str) -> list[dict]:
    trs = table.find_all("tr")
    if len(trs) < 2:
        return []
    out = []
    # trs[0] is a single-cell caption (e.g. "Standard Prepay Sims"),
    # trs[1] is the header row ("Transaction Description", "... Rate(s)").
    for tr in trs[2:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label, price_text = cells[0], cells[-1]
        for label_suffix, price, unit in _split_rate_cell(price_text):
            out.append(
                {
                    "item_name": f"{section} -- {label}{label_suffix}",
                    "price_local": price,
                    "unit": unit,
                }
            )
    return out


def fetch_fj_vodafone_prepay_rates(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    tables = soup.find_all("table")
    if len(tables) < 2:
        logger.warning(
            "[%s] expected >=2 rate tables, found %d", _SOURCE_KEY, len(tables)
        )
        return None

    parsed: list[dict] = []
    sections = ["Standard Prepay Sims", "Bula Packs & Tourist Sims"]
    for table, section in zip(tables, sections):
        parsed += _rows_from_table(table, section)

    if not parsed:
        logger.warning("[%s] no tariff rows parsed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
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
