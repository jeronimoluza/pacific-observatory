"""Jordan MEMR monthly fuel prices fetcher (PDF-based, pdfplumber).

Extraction strategy:
  - Construct predictable PDF URLs: p1-{month}-{year}.pdf
  - Download each PDF for months after cutoff
  - Parse single-page table with pdfplumber (selectable text)

Source: https://www.memr.gov.jo/En/List/Retail_Prices_Of_all_Petroleum_Products
  - Monthly PDFs at /EBV4.0/Root_Storage/AR/EB_List_Page/p1-{M}-{YYYY}.pdf
  - Confirmed available Jan 2021 – present (62/64 months HTTP 200)
  - One naming anomaly: May 2022 = p1-005-2022.pdf
"""

import io
import logging
import time
from datetime import date, datetime, timezone

import pandas as pd
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.memr.gov.jo/EBV4.0/Root_Storage/AR/EB_List_Page"

_COUNTRY = "Jordan"
_CURRENCY = "JOD"
_SOURCE_KEY = "jo_memr_monthly"

_FETCH_SLEEP = 10  # seconds between PDF downloads (site rate-limits aggressively)

# English product name (as it appears in the PDF) → (canonical name, unit)
# Prices in Fils/Liter need division by 1000 to convert to JOD.
_PRODUCT_MAP: dict[str, tuple[str, str, bool]] = {
    # (canonical_name, unit, is_fils)
    "Gasoline, Unleaded 90": ("Gasoline 90", "liter", True),
    "Gasoline, Unleaded 95": ("Gasoline 95", "liter", True),
    "Gasoline, Unleaded 98": ("Gasoline 98", "liter", True),
    "Diesel": ("Diesel", "liter", True),
    "Kerosene": ("Kerosene", "liter", True),
    "LPG (12.5 kg)": ("LPG 12.5kg", "cylinder", False),
    "LPG (50 kg)": ("LPG 50kg", "cylinder", False),
    "LPG (bulk) for Central Distribution": ("LPG Bulk", "ton", False),
    "Fuel Oil 3.5% sulfur": ("Fuel Oil 3.5%", "ton", False),
    "Fuel Oil (1% sulfur)": ("Fuel Oil 1%", "ton", False),
    "Avtur (Local Companies)": ("Avtur Local", "liter", True),
    "Avtur (Foreign Companies)": ("Avtur Foreign", "liter", True),
    "Avtur - (Charter Flights)": ("Avtur Charter", "liter", True),
    "Fuel Oil (Bunkers)": ("Fuel Oil Bunkers", "ton", False),
    "Diesel (Bunkers)": ("Diesel Bunkers", "liter", True),
    "Asphalt": ("Asphalt", "ton", False),
}

# Anomalous URL patterns: month → filename override
_URL_OVERRIDES: dict[tuple[int, int], str] = {
    (2022, 5): "p1-005-2022.pdf",
}


def _pdf_url(year: int, month: int) -> str:
    """Construct the PDF URL for a given year/month."""
    override = _URL_OVERRIDES.get((year, month))
    if override:
        return f"{_BASE_URL}/{override}"
    return f"{_BASE_URL}/p1-{month}-{year}.pdf"


def _months_since(cutoff: date) -> list[tuple[int, int]]:
    """Generate (year, month) pairs from the month after cutoff to now."""
    now = datetime.now(timezone.utc).date()
    months: list[tuple[int, int]] = []
    y, m = cutoff.year, cutoff.month
    # Start from the month after cutoff
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


_MAX_RETRIES = 3
_RETRY_DELAYS = [30, 60, 120]  # exponential backoff (seconds)
_DOWNLOAD_TIMEOUT = 300  # seconds per PDF (site is very slow, ~2-7 KB/s)


def _download_pdf(session: cffi_requests.Session, url: str) -> bytes | None:
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=_DOWNLOAD_TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except Exception:
            delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "[jo_memr] Attempt %d/%d failed for %s, retrying in %ds...",
                    attempt,
                    _MAX_RETRIES,
                    url,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.warning(
                    "[jo_memr] Failed to download %s after %d attempts",
                    url,
                    _MAX_RETRIES,
                )
    return None


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "").replace("٫", ".")
    # Remove any non-numeric characters except dot
    filtered = ""
    for ch in cleaned:
        if ch.isdigit() or ch == ".":
            filtered += ch
    if not filtered:
        return None
    try:
        val = float(filtered)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def _extract_from_pdf(pdf_bytes: bytes, obs_date: str) -> list[dict]:
    """Parse the price table from a single-page MEMR PDF."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("[jo_memr] pdfplumber not installed")
        return []

    rows: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return []
            page = pdf.pages[0]
            tables = page.extract_tables()
            if not tables:
                text = page.extract_text() or ""
                logger.warning("[jo_memr] No tables found in PDF, text: %s", text[:200])
                return []

            # Use the largest table (the price table)
            table = max(tables, key=len)

            for row in table:
                if not row or len(row) < 3:
                    continue
                # Try to match the English product name (first column)
                raw_product = (row[0] or "").strip()
                if not raw_product:
                    continue

                matched = _match_product(raw_product)
                if matched is None:
                    continue

                canonical, unit, is_fils = matched

                # Find the price cell — it's the numeric column
                price = None
                for cell in row[1:]:
                    p = _parse_price(cell or "")
                    if p is not None:
                        price = p
                        break

                if price is None:
                    continue

                # Convert Fils to JOD
                if is_fils:
                    price = price / 1000.0

                rows.append(
                    {
                        "observation_date": obs_date,
                        "country": _COUNTRY,
                        "fuel_product": canonical,
                        "price_local": round(price, 4),
                        "currency": _CURRENCY,
                        "unit": unit,
                        "source_key": _SOURCE_KEY,
                    }
                )

    except Exception:
        logger.exception("[jo_memr] Failed to parse PDF for %s", obs_date)
        return []

    return rows


def _match_product(raw: str) -> tuple[str, str, bool] | None:
    """Fuzzy-match a raw product name to our product map."""
    # Exact match first
    if raw in _PRODUCT_MAP:
        return _PRODUCT_MAP[raw]
    # Normalized match (collapse whitespace, case-insensitive)
    raw_lower = " ".join(raw.lower().split())
    for key, val in _PRODUCT_MAP.items():
        if " ".join(key.lower().split()) == raw_lower:
            return val
    # Substring match for partial names
    for key, val in _PRODUCT_MAP.items():
        key_lower = key.lower()
        if key_lower in raw_lower or raw_lower in key_lower:
            return val
    return None


def fetch_jo_memr(cutoff: date) -> pd.DataFrame | None:
    """Fetch Jordan MEMR monthly fuel prices from official PDFs."""
    session = cffi_requests.Session(impersonate="chrome")
    months = _months_since(cutoff)

    if not months:
        logger.info("[jo_memr] No new months after cutoff %s", cutoff)
        return None

    logger.info("[jo_memr] Fetching %d months (cutoff: %s)", len(months), cutoff)
    all_rows: list[dict] = []

    for i, (year, month) in enumerate(months):
        if i > 0:
            time.sleep(_FETCH_SLEEP)

        url = _pdf_url(year, month)
        obs_date = date(year, month, 1).strftime("%Y-%m-%d")

        pdf_bytes = _download_pdf(session, url)
        if pdf_bytes is None:
            logger.warning("[jo_memr] No PDF for %s", obs_date)
            continue

        rows = _extract_from_pdf(pdf_bytes, obs_date)
        if rows:
            all_rows.extend(rows)
            logger.info("[jo_memr] %s: %d products", obs_date, len(rows))
        else:
            logger.warning("[jo_memr] %s: no products extracted", obs_date)

    if not all_rows:
        logger.info("[jo_memr] No rows extracted")
        return None

    df = pd.DataFrame(all_rows)
    df = df.sort_values("observation_date").reset_index(drop=True)
    logger.info("[jo_memr] Returning %d rows", len(df))
    return df
