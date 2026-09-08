"""Macao SAR -- DSAT (Transport Bureau) official taxi fare schedule, snapshot.

DSAT (交通事務局, Direcção dos Serviços para os Assuntos de Tráfego) publishes
the regulated taxi tariff as a plain HTML table (not a PDF) at
https://www.dsat.gov.mo/dsat/subpage.aspx?a_id=1610600672&lang=en (English
UI language; the a_id itself is language-independent, only the surrounding
chrome changes with lang=en/tc/sc/pt). The table has two colspan=2 header
rows ("Fares (MOP)" and "Additional fee") separating a base-fare block from
a surcharge block -- both are read the same way here (item name in the
first <td>, MOP amount in the second), the header rows are simply not
numeric in their second column and drop out naturally.

Verified live 2026-09-06: 200, clean two-column HTML table,
`pandas.read_html` parses it directly with zero cleanup beyond dropping the
two section-header rows. Distinct item rows recovered: "First 1600m"
21.00, "Every 220m" 2.00, waiting-time surcharge 2.00, baggage surcharge
3.00, Taipa-Coloane 2.00, Macao-Coloane 5.00, airport/ferry/port-boarding
surcharge 8.00, University of Macau Hengqin-campus surcharge 5.00 -- 8 rows
total.

No prior-tariff archive exists on the page (current schedule only) --
snapshots the CURRENT table each run (period_kind: effective_from). The
page's own "Last modified" footer date is used as the effective date.

Currency: MOP, matches countries.yaml. coicop_classification:
source_curated -- COICOP 07.3.2.2 (passenger transport by taxi and hired
vehicle with driver), single narrow class for the whole schedule.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.dsat.gov.mo/dsat/subpage.aspx?a_id=1610600672&lang=en"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_dsat_taxi_fares"
_COICOP_CODE = "07.3.2.2"
_IDENT = ["source_key", "observation_date", "item_name"]

_LAST_MODIFIED_RE = re.compile(r"Last modified:\s*(\d{2})-(\d{2})-(\d{4})")
_PRICE_RE = re.compile(r"^\d+(?:\.\d+)?$")


def fetch_mo_dsat_taxi_fares(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    m = _LAST_MODIFIED_RE.search(resp.text)
    if m:
        dd, mm, yyyy = m.groups()
        effective_from = date(int(yyyy), int(mm), int(dd))
    else:
        effective_from = date.today()

    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no HTML table found: %s", _SOURCE_KEY, exc)
        return None

    parsed: list[dict] = []
    for tbl in tables:
        if tbl.shape[1] != 2:
            continue
        for _, row in tbl.iterrows():
            name = str(row.iloc[0]).strip()
            raw_price = str(row.iloc[1]).strip()
            if not _PRICE_RE.match(raw_price):
                continue  # section-header row or malformed cell
            try:
                price = float(raw_price)
            except ValueError:
                continue
            if price <= 0 or not name or name.lower() == "nan":
                continue
            parsed.append({"item_name": name[:200], "price_local": price})

    if not parsed:
        logger.warning("[%s] no fare rows parsed from %s", _SOURCE_KEY, _PAGE_URL)
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
            "unit": "fare",
            "source_url": _PAGE_URL,
            "notes": "DSAT official regulated taxi fare schedule",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
