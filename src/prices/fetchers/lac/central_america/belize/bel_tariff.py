"""BEL (Belize Electricity Limited) -- household electricity tariffs.

The Rate Schedule page (bel.com.bz/Rate_Schedule.aspx, an old absolute-
positioned ASPX layout) states its own effective period in a plain
sentence ("...for the period January 1, 2026, to June 30, 2026.") and
renders the rate tables as plain (if deeply nested) HTML <table> markup
that `pandas.read_html` parses without any special handling -- no
Playwright needed. `pandas.read_html` returns 80+ tables from the page
(most are 1x1 layout-only tables from the nested-table styling); Social,
Residential and Commercial 1 all share ONE physical <table> element as a
single combined 3-column [Block, kWhrs, Rate] frame with "SOCIAL RATES" /
"RESIDENTIAL RATES" / "COMMERCIAL 1 ..." header cells inside it -- a naive
match on "RESIDENTIAL RATES" anywhere in that table's first column pulls in
Social's and Commercial 1's identically-labeled "1"/"2"/"3"/"Minimum
Charge" rows too (confirmed live 2026-09-01: 5 of 11 rows from the naive
approach were exact-duplicate hashes). Rows are sliced from the header cell
of each named section down to that section's own "Minimum Charge" row.

Two household-facing classes are emitted: RESIDENTIAL RATES (the general
household tariff) and SOCIAL RATES (BEL's lifeline/low-consumption
household bracket, a single 0-60 kWh block + its own minimum charge) --
both are consumer electricity tariffs, not business tariffs. Commercial
1/2, Industrial 1/2 and Street Lights are visible on the same page but are
a different, non-household customer class, out of scope for a
household-facing PPP basket.

Whole source is COICOP 04.5.1 (Electricity) -- source_curated, single
constant, no per-item map needed.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_RATE_URL = "https://www.bel.com.bz/Rate_Schedule.aspx"
_COUNTRY = "Belize"
_CURRENCY = "BZD"
_SOURCE_KEY = "bz_bel_tariff"
_COICOP = "04.5.1"

_EFFECTIVE_RE = re.compile(
    r"for the period\s+([A-Za-z]+ \d{1,2},\s*\d{4}),?\s*to\s*([A-Za-z]+ \d{1,2},\s*\d{4})"
)

# (section header text as it appears in the table, human-readable label
# prefix for item_name)
_HOUSEHOLD_SECTIONS = [
    ("RESIDENTIAL RATES", "Residential"),
    ("SOCIAL RATES", "Social/lifeline residential"),
]

_IDENT = ["source_key", "effective_from", "item_name"]


def _parse_effective_from(html_text: str) -> date | None:
    m = _EFFECTIVE_RE.search(html_text)
    if not m:
        return None
    try:
        return pd.to_datetime(m.group(1)).date()
    except (ValueError, TypeError):
        return None


def _find_combined_rate_table(tables: list[pd.DataFrame]) -> pd.DataFrame | None:
    for t in tables:
        if t.shape[1] != 3 or t.shape[0] < 4:
            continue
        first_col_text = " ".join(str(v) for v in t.iloc[:, 0].tolist()).upper()
        if "RESIDENTIAL RATES" in first_col_text:
            return t
    return None


def _extract_section_rows(combined: pd.DataFrame, header_text: str) -> list:
    """Slice rows from `header_text`'s header cell to its own Minimum Charge row.

    Social/Residential/Commercial share one physical table; without this
    slice, a section's "1"/"2"/"3"/"Minimum Charge" block labels collide
    with the identically-labeled rows of every other section in the table.
    """
    section_rows = []
    in_section = False
    for _, r in combined.iterrows():
        block = str(r.iloc[0]).strip()
        if block.upper() == header_text:
            in_section = True
            continue
        if not in_section:
            continue
        if block == "Block":
            continue
        section_rows.append(r)
        if block.lower() == "minimum charge":
            break
    return section_rows


def fetch_bz_bel_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_RATE_URL, timeout=30)
    resp.raise_for_status()
    html_text = resp.text

    effective_from = _parse_effective_from(html_text)
    if effective_from is None:
        logger.warning(
            "[%s] could not parse effective-period sentence -- aborting", _SOURCE_KEY
        )
        return None
    if effective_from <= cutoff:
        return None

    tables = pd.read_html(io.StringIO(html_text))
    combined = _find_combined_rate_table(tables)
    if combined is None:
        logger.warning("[%s] rate table not found on page", _SOURCE_KEY)
        return None

    rows = []
    for header_text, label in _HOUSEHOLD_SECTIONS:
        for r in _extract_section_rows(combined, header_text):
            block = str(r.iloc[0]).strip()
            rate_raw = str(r.iloc[2]).strip()
            rate_match = re.search(r"\$?\s*([\d.]+)", rate_raw)
            if not rate_match:
                continue
            try:
                rate = float(rate_match.group(1))
            except ValueError:
                continue
            if block.lower() == "minimum charge":
                item_name = f"{label} minimum charge"
                unit = "month"
            else:
                kwh_range = str(r.iloc[1]).strip()
                item_name = f"{label} electricity, block {block} ({kwh_range} kWh)"
                unit = "kWh"
            row = {
                "observation_date": effective_from.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": rate,
                "currency": _CURRENCY,
                "unit": unit,
                "coicop_code": _COICOP,
                "effective_from": effective_from.isoformat(),
                "source_url": _RATE_URL,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
