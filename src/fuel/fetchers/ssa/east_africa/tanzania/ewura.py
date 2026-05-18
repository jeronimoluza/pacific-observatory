"""EWURA Tanzania — monthly Cap Prices for Petroleum Products.

EWURA publishes a public-notice PDF on the first Wednesday of every month
at https://www.ewura.go.tz/publications/petroleum-price (paginated index).
PDF filenames follow ``en-<unix_ts>-Cap Prices ...Month YYYY.pdf``.

The first page contains a clean *Table 1: Retail Prices — TZS/Litre* with
three port rows (Dar es Salaam, Tanga, Mtwara) × three product columns
(Petrol, Diesel, Kerosene). That table is the canonical headline series.

Effective date is parsed from the body line
    "EFFECTIVE WEDNESDAY, <Dth> <Month> <YYYY>"
falling back to the filename's month token if the body string is missing.
"""

import io
import logging
import re
import time
from datetime import date
from urllib.parse import unquote, urljoin

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.ewura.go.tz"
_INDEX_PATH = "/publications/petroleum-price"
_COUNTRY = "Tanzania"
_CURRENCY = "TZS"
_SOURCE_KEY = "ewura_tz_monthly"

_PDF_HREF_RE = re.compile(
    r"""href=["']([^"']*?/uploads/documents/[^"']+?\.pdf)["']""", re.I
)
_CAP_PRICES_RE = re.compile(r"cap[\s_-]+prices", re.IGNORECASE)
# Drop Swahili variants — title says "Bei Kikomo", or "Kiswahili" appears in
# the filename, or the month name is in Swahili (e.g. "Oktoba").
_EXCLUDE_SWAHILI_RE = re.compile(
    r"\bBei[\s_-]+Kikomo|Kiswahili|Oktoba|Januari|Februari|Machi|Aprili|"
    r"Mei|Juni|Julai|Agosti|Septemba|Novemba|Disemba",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    r"EFFECTIVE\s+\w+,?\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)
_FILENAME_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b[\s\-_]*(\d{4})",
    re.IGNORECASE,
)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_PORTS = ("Dar es Salaam", "Tanga", "Mtwara")
_PRODUCTS = ("Petrol", "Diesel", "Kerosene")

_THROTTLE_S = 2.0
_MAX_INDEX_PAGES = 15


def _discover_pdfs(session) -> list[str]:
    """Walk index pages and return absolute Cap-Prices PDF URLs."""
    seen: set[str] = set()
    for page in range(_MAX_INDEX_PAGES):
        if page > 0:
            time.sleep(_THROTTLE_S)
        suffix = "" if page == 0 else f"?page={page}"
        url = f"{_BASE_URL}{_INDEX_PATH}{suffix}"
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        hrefs = sorted(set(_PDF_HREF_RE.findall(resp.text)))
        if not hrefs:
            logger.info("[ewura_tz] page=%d empty — stopping", page)
            break
        new_count = 0
        for href in hrefs:
            absurl = urljoin(_BASE_URL, href)
            filename = unquote(absurl.rsplit("/", 1)[-1])
            if _EXCLUDE_SWAHILI_RE.search(filename):
                continue
            if not _CAP_PRICES_RE.search(filename):
                continue
            if absurl in seen:
                continue
            seen.add(absurl)
            new_count += 1
        logger.info(
            "[ewura_tz] page=%d total=%d new_cap_pdfs=%d", page, len(hrefs), new_count
        )
        if new_count == 0 and page >= 2:
            # Two consecutive pages with no new cap-price PDFs → stop
            break
    return sorted(seen)


def _parse_effective_date(text: str, filename: str) -> date | None:
    """Return the effective date from page-0 text; fall back to filename."""
    m = _EFFECTIVE_RE.search(text)
    if m:
        day, month_name, year = m.group(1), m.group(2), m.group(3)
        month = _MONTHS.get(month_name.lower())
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                pass
    m = _FILENAME_MONTH_RE.search(filename)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            try:
                return date(int(m.group(2)), month, 1)
            except ValueError:
                pass
    return None


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return val if val > 0 else None


def _extract_table1_rows(page) -> dict[str, dict[str, float]]:
    """Parse the first 'Retail Prices' table on page 0.

    Returns a dict: { port_name: { product: price } }.
    """
    tables = page.extract_tables() or []
    out: dict[str, dict[str, float]] = {}
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [c or "" for c in table[0]]
        joined_header = " ".join(header).lower()
        # Retail Prices header has 'port' + product names
        if "port" not in joined_header:
            continue
        # Must mention petrol AND diesel to qualify as a price header
        if not (("petrol" in joined_header) and ("diesel" in joined_header)):
            continue
        # Find the column index of each product by scanning non-None cells
        for row in table[1:]:
            if not row:
                continue
            non_empty = [c for c in row if c]
            if len(non_empty) < 4:
                continue
            port_name = non_empty[0].strip()
            # Reject wholesale rows (have decimal prices like 3,972.13)
            # and prefer the first table; if 'out' already has this port,
            # we've moved on to wholesale — skip.
            if port_name not in _PORTS:
                continue
            if port_name in out:
                continue
            prices = [_parse_price(c) for c in non_empty[1:4]]
            if any(p is None for p in prices):
                continue
            out[port_name] = dict(zip(_PRODUCTS, prices))
        if out:
            # Stop after the first qualifying retail table
            return out
    return out


def _extract_from_pdf(pdf_bytes: bytes, filename: str) -> list[dict]:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[ewura_tz] pdfplumber not installed")
        return []

    rows: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return []
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            obs_date = _parse_effective_date(text, filename)
            if obs_date is None:
                logger.warning(
                    "[ewura_tz] could not parse effective date for %s", filename
                )
                return []
            port_prices = _extract_table1_rows(first_page)
            if not port_prices:
                logger.warning(
                    "[ewura_tz] no Table 1 found in %s (date %s)", filename, obs_date
                )
                return []
            iso = obs_date.strftime("%Y-%m-%d")
            for port, prices in port_prices.items():
                for product, price in prices.items():
                    rows.append(
                        {
                            "observation_date": iso,
                            "country": _COUNTRY,
                            "fuel_product": product,
                            "price_local": price,
                            "currency": _CURRENCY,
                            "unit": "L",
                            "source_key": _SOURCE_KEY,
                            "city": port,
                        }
                    )
    except Exception:
        logger.exception("[ewura_tz] failed to parse PDF %s", filename)
        return []
    return rows


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=90)
        if resp.status_code != 200:
            logger.warning("[ewura_tz] %s → HTTP %d", url, resp.status_code)
            return None
        if not resp.content or resp.content[:4] != b"%PDF":
            logger.warning("[ewura_tz] %s → not a PDF", url)
            return None
        return resp.content
    except Exception:
        logger.exception("[ewura_tz] download failed %s", url)
        return None


def fetch_ewura_tz(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    pdf_urls = _discover_pdfs(session)
    if not pdf_urls:
        logger.info("[ewura_tz] No cap-price PDFs found")
        return None

    logger.info("[ewura_tz] %d candidate PDFs", len(pdf_urls))
    all_rows: list[dict] = []
    for i, url in enumerate(pdf_urls):
        if i > 0:
            time.sleep(_THROTTLE_S)
        filename = unquote(url.rsplit("/", 1)[-1])
        # Quick filename-month gate to skip PDFs older than cutoff.
        m = _FILENAME_MONTH_RE.search(filename)
        if m:
            mo = _MONTHS.get(m.group(1).lower())
            if mo:
                try:
                    file_date = date(int(m.group(2)), mo, 28)
                    if file_date <= cutoff:
                        continue
                except ValueError:
                    pass
        pdf_bytes = _download_pdf(session, url)
        if pdf_bytes is None:
            continue
        rows = _extract_from_pdf(pdf_bytes, filename)
        # Filter on actual parsed date too (filename month is approximate).
        kept = [r for r in rows if r["observation_date"] > cutoff.strftime("%Y-%m-%d")]
        if not kept:
            continue
        all_rows.extend(kept)
        logger.info(
            "[ewura_tz] %s → %d rows (date %s)",
            filename[:60],
            len(kept),
            kept[0]["observation_date"],
        )

    if not all_rows:
        logger.info("[ewura_tz] No new rows after cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(all_rows)
        .drop_duplicates(subset=["observation_date", "city", "fuel_product"])
        .sort_values(["observation_date", "city", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[ewura_tz] %d total rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_ewura_tz"]
