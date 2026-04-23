"""Israel Ministry of Energy monthly fuel price fetcher (Excel-based).

Extraction strategy:
  - Construct predictable XLS URLs: price-structure-{month}-{year}.xls
  - Download each file for months after cutoff
  - Parse Sheet 1 for regulated maximum prices (gasoline, fuel oil, bitumen, LPG)

Source: https://www.gov.il/he/pages/price_stucture
  - Monthly Excel files at BlobFolder/generalpage/price-structure-{year}/he/
  - Confirmed available Jan 2024 – present
  - Product set expanded around Apr 2025 (3→8 refinery-gate products)
  - Some months have column-offset variation (e.g., Nov 2024)
"""

import io
import logging
import time
from datetime import date, datetime, timezone

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://www.gov.il/BlobFolder/generalpage"
    "/price-structure-{year}/he/price-structure-{month}-{year}.xls"
)

_COUNTRY = "Israel"
_CURRENCY = "ILS"
_SOURCE_KEY = "il_gov_energy"

_FETCH_SLEEP = 1  # seconds between downloads
_MIN_FILE_SIZE = 10_000  # bytes — anything smaller is an error page
_EARLIEST = date(2023, 12, 1)

# Hebrew product name → (English canonical name, unit)
_REFINERY_PRODUCTS: dict[str, tuple[str, str]] = {
    "מזוט כבד 4000 3.5%": ("Heavy Fuel Oil 3.5%S", "ton"),
    "מזוט כבד בעל תכולת גופרית של 1%": ("Heavy Mazut 1%S", "ton"),
    "מזוט כבד בעל תכולת גופרית של 0.5%": ("Heavy Mazut 0.5%S", "ton"),
    "מזוט קל בעל תכולת גופרית של 1%": ("Light Mazut 1%S", "ton"),
    "מזוט קל בעל תכולת גופרית של 0.5%": ("Light Mazut 0.5%S", "ton"),
    "זפת 80/100": ("Bitumen 80/100", "ton"),
    "זפת ה.ב.": ("HB Bitumen", "ton"),
    'מחיר קובע לגפ"מ': ("LPG Reference", "ton"),
    'מחיר ייבוא גפ"מ': ("LPG Import", "ton"),
}

# Gasoline row marker (exclude Eilat)
_GASOLINE_MARKER = "מחיר לליטר בתחנה"
_EILAT_MARKER = "אילת"


def _months_since(cutoff: date) -> list[tuple[int, int]]:
    """Generate (year, month) pairs from the month after cutoff to now."""
    start = max(cutoff, _EARLIEST)
    now = datetime.now(timezone.utc).date()
    months: list[tuple[int, int]] = []
    y, m = start.year, start.month
    m += 1
    if m > 12:
        m = 1
        y += 1
    while date(y, m, 1) <= now:
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _xls_url(year: int, month: int) -> str:
    return _BASE_URL.format(year=year, month=month)


def _download_xls(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        if len(resp.content) < _MIN_FILE_SIZE:
            return None
        return resp.content
    except Exception:
        logger.warning("[il_gov] Failed to download %s", url)
        return None


def _extract_date(xls_bytes: bytes, year: int, month: int) -> str:
    """Read effective date from Sheet 2, fall back to year/month."""
    try:
        df = pd.read_excel(
            io.BytesIO(xls_bytes),
            sheet_name="2",
            header=None,
            engine="xlrd",
        )
        for _, row in df.iterrows():
            for cell in row:
                if isinstance(cell, datetime):
                    return cell.strftime("%Y-%m-%d")
    except Exception:
        pass
    return date(year, month, 1).strftime("%Y-%m-%d")


def _find_numeric(row: pd.Series) -> float | None:
    """Find the last numeric value > 1 in a row (skips column indices)."""
    result = None
    for val in row:
        if isinstance(val, (int, float)) and pd.notna(val) and val > 1:
            result = float(val)
    return result


def _parse_sheet1(xls_bytes: bytes) -> list[dict]:
    """Extract fuel product prices from Sheet 1."""
    try:
        df = pd.read_excel(
            io.BytesIO(xls_bytes),
            sheet_name="1",
            header=None,
            engine="xlrd",
        )
    except Exception:
        logger.warning("[il_gov] Failed to read Sheet 1")
        return []

    rows: list[dict] = []

    for idx, row in df.iterrows():
        text_cells = []
        for val in row:
            if isinstance(val, str):
                text_cells.append(val.strip())

        row_text = " ".join(text_cells)

        # Gasoline: find "מחיר לליטר בתחנה" excluding Eilat
        if _GASOLINE_MARKER in row_text and _EILAT_MARKER not in row_text:
            price = _find_numeric(row)
            if price is not None and price < 50:
                rows.append(
                    {
                        "fuel_product": "Gasoline 95",
                        "price_local": round(price, 2),
                        "unit": "L",
                    }
                )

        # Refinery-gate and LPG products
        for hebrew_name, (english_name, unit) in _REFINERY_PRODUCTS.items():
            if hebrew_name in row_text:
                price = _find_numeric(row)
                if price is not None:
                    rows.append(
                        {
                            "fuel_product": english_name,
                            "price_local": round(price, 2),
                            "unit": unit,
                        }
                    )

    return rows


def fetch_il_gov_energy(cutoff: date) -> pd.DataFrame | None:
    """Fetch Israel fuel prices from Ministry of Energy monthly Excel files."""
    session = make_session()
    months = _months_since(cutoff)

    if not months:
        logger.info("[il_gov] No new months after cutoff %s", cutoff)
        return None

    logger.info("[il_gov] Fetching %d months (cutoff: %s)", len(months), cutoff)
    all_rows: list[dict] = []

    for i, (year, month) in enumerate(months):
        if i > 0:
            time.sleep(_FETCH_SLEEP)

        url = _xls_url(year, month)
        xls_bytes = _download_xls(session, url)
        if xls_bytes is None:
            logger.debug("[il_gov] No file for %d-%02d", year, month)
            continue

        obs_date = _extract_date(xls_bytes, year, month)
        products = _parse_sheet1(xls_bytes)

        for p in products:
            all_rows.append(
                {
                    "observation_date": obs_date,
                    "country": _COUNTRY,
                    "fuel_product": p["fuel_product"],
                    "price_local": p["price_local"],
                    "currency": _CURRENCY,
                    "unit": p["unit"],
                    "source_key": _SOURCE_KEY,
                }
            )

        logger.info("[il_gov] %s: %d products", obs_date, len(products))

    if not all_rows:
        logger.info("[il_gov] No rows extracted")
        return None

    df = pd.DataFrame(all_rows)
    df = df.sort_values("observation_date").reset_index(drop=True)
    logger.info("[il_gov] Returning %d rows", len(df))
    return df
