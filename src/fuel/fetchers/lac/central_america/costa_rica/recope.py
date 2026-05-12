"""Costa Rica RECOPE historical retail fuel price fetcher.

Source: https://www.recope.go.cr/productos/precios-nacionales/historicos/

The page hosts three XLS files updated monthly under
  wp-content/uploads/{YYYY}/{MM}/PRECIOS-HISTORICOS-CONSUMIDOR-FINAL.xls
We discover the latest file by probing recent year/month combinations.

Each row in the XLS represents a price-change event (irregular cadence),
not a calendar tick. The "Cons.Final" sub-column per product gives the
consumer final price in CRC/L. Columns are fixed-position (see XLS_COLS).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://www.recope.go.cr/wp-content/uploads/{year}/{month:02d}/"
    "PRECIOS-HISTORICOS-CONSUMIDOR-FINAL.xls"
)
_COUNTRY = "Costa Rica"
_CURRENCY = "CRC"
_SOURCE_KEY = "cr_recope_historical"

# Fixed column indices for "Precio Cons.Final" of each product in the XLS.
_XLS_COLS: dict[str, int] = {
    "GASOLINA SUPER": 4,
    "GASOLINA PLUS 91": 7,
    "DIESEL 50": 10,
    "KEROSENO": 13,
}

_SPANISH_MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SETIEMBRE": 9,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}

_DATE_RE = re.compile(
    r"(\d{1,2})\s*DE\s*([A-ZÉÚÍÓÁ]+)[,\s]*(?:DEL?\s*)?(\d{4})",
    re.IGNORECASE,
)


def _parse_spanish_date(raw: str) -> date | None:
    if not isinstance(raw, str):
        return None
    match = _DATE_RE.search(raw.strip().upper())
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)
    month = _SPANISH_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, day)
    except ValueError:
        return None


def _discover_xls_bytes(session) -> bytes | None:
    """Walk back from this month to find the latest RECOPE archive."""
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    for _ in range(24):
        url = _BASE_URL.format(year=year, month=month)
        try:
            resp = session.get(url, timeout=60)
        except Exception:
            resp = None
        if resp is not None and resp.status_code == 200 and len(resp.content) > 50_000:
            logger.info("[cr_recope] Using %s", url)
            return resp.content
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    logger.warning("[cr_recope] Could not locate RECOPE XLS archive")
    return None


def fetch_cr_recope(cutoff: date) -> pd.DataFrame | None:
    """Fetch Costa Rica retail fuel prices from the RECOPE historical XLS."""
    session = make_session()
    raw = _discover_xls_bytes(session)
    if raw is None:
        return None

    try:
        df = pd.read_excel(io.BytesIO(raw), header=None)
    except Exception:
        logger.exception("[cr_recope] Failed to parse XLS")
        return None

    rows: list[dict] = []
    # First 5 rows are header/banner; data starts at row 5.
    for idx in range(5, len(df)):
        raw_date = df.iat[idx, 0]
        obs_date = _parse_spanish_date(raw_date)
        if obs_date is None:
            continue
        if obs_date <= cutoff:
            continue
        for product, col in _XLS_COLS.items():
            value = df.iat[idx, col]
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if pd.isna(price) or price <= 0:
                continue
            rows.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )

    if not rows:
        logger.info("[cr_recope] No new rows after cutoff %s", cutoff)
        return None

    out = pd.DataFrame(rows).sort_values("observation_date").reset_index(drop=True)
    logger.info("[cr_recope] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
