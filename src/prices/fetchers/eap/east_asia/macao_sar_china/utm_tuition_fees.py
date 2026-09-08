"""Macao SAR -- UTM (Macao University of Tourism) undergraduate tuition fee
schedule, snapshot.

UTM's homepage has no direct fees link -- it cross-links to a shared
admissions portal at
www.utm.edu.mo/admission/en/undergraduate_programmes/fees/index.html
(found via www.utm.edu.mo/iftadmission/degree-programmes; UTM absorbed the
former Institute for Tourism Studies, IFT, and the two institutions still
share admissions infrastructure -- ift.edu.mo links resolve on the same
domain). Verified live 2026-09-06: 200, a single clean HTML table, no PDF,
no JS rendering needed.

The table has one messy merged-header first row (repeats "Bachelor's
Degree Programmes" across every column -- an artifact of a rowspan header
cell that `pandas.read_html` doesn't collapse cleanly) which is dropped by
matching cells that equal the column's own first value; the next 3 rows
are genuinely tabular: {Annual tuition fee, Full tuition fee within normal
study duration, Tuition fee per credit} x {Macao SAR students, Mainland
China/HK/Taiwan students, other places' students}. Currency prefix "MOP"
is stripped with a regex, not assumed positionally.

No PDF or explicit effective-date field -- the page's own heading ("Tuition
Fee of Academic Year 2026/2027") is parsed for the academic year and
effective_from is set to that year's Sept 1 start, consistent with the
sibling um_tuition_fees.py fetcher's convention for the same gap.

Currency: MOP, matches countries.yaml. coicop_classification:
source_curated -- COICOP 10.4.0.0 (tertiary education).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import StringIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.utm.edu.mo/admission/en/undergraduate_programmes/fees/index.html"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_utm_tuition_fees"
_COICOP_CODE = "10.4.0.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_MOP_RE = re.compile(r"MOP\s*([\d,]+(?:\.\d+)?)")
_ACADEMIC_YEAR_RE = re.compile(r"Academic Year (\d{4})/(\d{4})")

_UNIT_BY_FEE_TYPE = {
    "Annual tuition fee": "year",
    "Full tuition fee within normal study duration": "programme",
    "Tuition fee per credit": "credit",
}


def fetch_mo_utm_tuition_fees(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    yr_m = _ACADEMIC_YEAR_RE.search(resp.text)
    effective_from = date(int(yr_m.group(1)), 9, 1) if yr_m else date.today()
    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    try:
        tables = pd.read_html(StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no HTML tables found: %s", _SOURCE_KEY, exc)
        return None

    tbl = next((t for t in tables if "Programme" in str(t.columns[0])), None)
    if tbl is None:
        logger.warning("[%s] fee table not found on %s", _SOURCE_KEY, _PAGE_URL)
        return None

    student_cols = list(tbl.columns[1:])
    parsed: list[dict] = []
    for _, row in tbl.iterrows():
        fee_type = str(row.iloc[0]).strip()
        if fee_type not in _UNIT_BY_FEE_TYPE:
            continue  # the spurious merged-header row falls out here
        unit = _UNIT_BY_FEE_TYPE[fee_type]
        for col in student_cols:
            m = _MOP_RE.search(str(row[col]))
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            item_name = f"{fee_type} ({col})"
            parsed.append({"item_name": item_name[:200], "price_local": price, "unit": unit})

    if not parsed:
        logger.warning("[%s] no fee rows parsed from %s", _SOURCE_KEY, _PAGE_URL)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "source_url": _PAGE_URL,
            "notes": "UTM Bachelor's Degree Programmes tuition fee schedule",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
