"""STC Mauritius — Petroleum Pricing Committee retail prices.

Single HTML table at https://www.stcmu.com/ppm/retail-prices listing every
APM (Automatic Pricing Mechanism) price revision since April 2004 plus a
pre-APM baseline row dated 01 July 2002. Columns:

    DATE (WEF) | Mogas (Rs/Litre) | Gas Oil (Rs/Litre)

Cadence: monthly since Nov-2008 (quarterly Apr-2004 → Oct-2008). The table
holds the entire series — no pagination, no JS — so a single GET reconstructs
full history.

Date strings mix formats: `2-Apr-04`, `03-March-2026`, `16-April-2026`. We
use dateutil with `dayfirst=True` to handle all variants and skip
unparseable summary rows (e.g. "Before APM (01 July 2002)").
"""

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from core.http import make_session

logger = logging.getLogger(__name__)

_URL = "https://www.stcmu.com/ppm/retail-prices"
_COUNTRY = "Mauritius"
_CURRENCY = "MUR"
_SOURCE_KEY = "stc_mu_monthly"

_PRODUCTS = {
    "Mogas": "Mogas",
    "Gas Oil": "Gas Oil",
}


def _parse_date(text: str) -> date | None:
    if not text or not text[0].isdigit():
        return None
    try:
        return dateparser.parse(text, dayfirst=True).date()
    except (ValueError, OverflowError, dateparser.ParserError):
        return None


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        v = float(cleaned)
    except ValueError:
        return None
    return v if v > 0 else None


def fetch_stc_mu(cutoff: date) -> pd.DataFrame | None:
    """Fetch the full Mauritius STC table; return rows newer than cutoff."""
    session = make_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table")
    if table is None:
        logger.warning("[stc_mu] No table found at %s", _URL)
        return None

    rows_out: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or not any(cells):
            continue
        if cells[0].upper().startswith("DATE"):
            continue  # header row
        if cells[0].lower().startswith("rs/"):
            continue  # unit-only sub-header
        obs = _parse_date(cells[0])
        if obs is None or obs <= cutoff:
            continue
        if len(cells) < 3:
            continue
        iso = obs.strftime("%Y-%m-%d")
        for col_idx, raw_label in enumerate(("Mogas", "Gas Oil"), start=1):
            if col_idx >= len(cells):
                continue
            price = _parse_price(cells[col_idx])
            if price is None:
                continue
            rows_out.append(
                {
                    "observation_date": iso,
                    "country": _COUNTRY,
                    "fuel_product": _PRODUCTS[raw_label],
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                }
            )

    if not rows_out:
        logger.info("[stc_mu] No rows after cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(rows_out)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[stc_mu] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_stc_mu"]
