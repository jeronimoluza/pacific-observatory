"""State Statistics Service of Ukraine (ukrstat.gov.ua) — consumer price index.

The IMF/SDDS archive page publishes the all-items consumer price index as a
server-rendered HTML table: rows are years, columns are the 12 months, values
are the cumulative CPI level on base 2001=100 (e.g. Dec 2024 ≈ 489). This is the
benchmark index series for Ukraine, used to anchor the price-level work.

analytical_role: cpi_benchmark -> emits IndexObservation rows (index_value /
index_base_period), routed to index_observations.csv by the writer.
coicop_classification: publisher_labeled — this table is the all-items index, so
coicop_code is "00" (all-items); a per-division breakdown would come from the
SDMX API (stat.gov.ua/sdmx) and is left for a later pass.

The published cells carry OCR-style stray spaces inside numbers ("4 40 , 1" =
440.1), so all whitespace is stripped before parsing the comma-decimal value.
ukrstat can TCP-drop / WAF non-UA clients, so we fetch via curl_cffi
(impersonate=chrome). The page is cp1251-encoded.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.ukrstat.gov.ua/imf/arhiv/isc_e.htm"
_COUNTRY = "Ukraine"
_SOURCE_KEY = "ua_ukrstat_cpi"
_COICOP = "00"  # all-items CPI
_BASE_PERIOD = "2001=100"

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_WS_RE = re.compile(r"\s+")

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _parse_value(text: str) -> float | None:
    cleaned = _WS_RE.sub("", text).replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        return None
    v = float(cleaned)
    return v if 50.0 < v < 5000.0 else None


def fetch_ua_ukrstat_cpi(cutoff: date) -> pd.DataFrame | None:
    resp = cffi_requests.get(_URL, timeout=30, impersonate="chrome")
    resp.raise_for_status()
    html = resp.content.decode("cp1251", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table")
    if table is None:
        logger.warning("ukrstat_cpi: no table found")
        return None

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        ym = _YEAR_RE.search(cells[0])
        if not ym:
            continue  # header / caption row
        year = int(ym.group(0))
        # cells[1:] are the 12 monthly index values (some may be blank/future).
        for month, raw in enumerate(cells[1:13], start=1):
            value = _parse_value(raw)
            if value is None:
                continue
            obs_date = f"{year:04d}-{month:02d}-01"
            row = {
                "observation_date": obs_date,
                "period_kind": "monthly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "index_value": value,
                "index_base_period": _BASE_PERIOD,
                "source_url": _URL,
                "notes": "All-items consumer price index",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("ukrstat_cpi: no index rows parsed")
        return None
    logger.info("ukrstat_cpi: parsed %d monthly index points", len(rows))
    return pd.DataFrame(rows)
