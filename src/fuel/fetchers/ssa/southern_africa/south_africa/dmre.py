"""South Africa DMRE fuel-price history PDFs."""

from __future__ import annotations

import io
import logging
import re
import time
import warnings
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import urllib3

from core.http import make_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_ARCHIVE_URL = "https://www.energy.gov.za/files/esources/petroleum/petroleum_arch.html"
_COUNTRY = "South Africa"
_CURRENCY = "ZAR"
_SOURCE_KEY = "dmre_za_fuel_history"
_THROTTLE_S = 0.5

_PDF_HREF_RE = re.compile(r'href="([^"]*Fuel-Price-History\.pdf)"', re.I)
_YEAR_RE = re.compile(r"Fuel Price History:\s*(20\d{2}|19\d{2})", re.I)
_URL_YEAR_RE = re.compile(
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)[-_]?(20\d{2}|19\d{2})|(?:Dec-)(20\d{2}|19\d{2})",
    re.I,
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_PRODUCT_COLUMNS = [
    ("Petrol 93", "Inland"),
    ("Petrol 95", "Coast"),
    ("Petrol 95", "Inland"),
    ("Diesel 0.05% sulphur", "Coast"),
    ("Diesel 0.05% sulphur", "Inland"),
    ("Illuminating Paraffin", "Coast"),
    ("Illuminating Paraffin", "Inland"),
]


def _parse_number(raw: str | None) -> float | None:
    if raw is None or raw.strip() in {"", "-"}:
        return None
    try:
        cents = float(raw.replace(",", "").strip())
    except ValueError:
        return None
    return round(cents / 100.0, 4) if cents > 0 else None


def _year_from_url(url: str) -> int | None:
    m = _URL_YEAR_RE.search(url)
    if not m:
        return None
    val = next((g for g in m.groups() if g), None)
    return int(val) if val else None


def _discover_pdfs(session) -> list[str]:
    try:
        resp = session.get(_ARCHIVE_URL, timeout=60, verify=False)
    except Exception:
        logger.exception("[dmre_za] archive fetch failed")
        return []
    if resp.status_code != 200:
        logger.warning("[dmre_za] archive HTTP %d", resp.status_code)
        return []
    urls = {urljoin(_ARCHIVE_URL, href) for href in _PDF_HREF_RE.findall(resp.text)}
    # Known static URLs are useful when the archive strips hrefs in some mirrors.
    urls.update(
        {
            "https://www.energy.gov.za/files/esources/petroleum/July2024/Fuel-Price-History.pdf",
            "https://www.energy.gov.za/files/esources/petroleum/October2023/Fuel-Price-History.pdf",
            "https://www.energy.gov.za/files/esources/petroleum/October2022/Fuel-Price-History.pdf",
            "https://www.energy.gov.za/files/esources/petroleum/October2021/Fuel-Price-History.pdf",
            "https://www.energy.gov.za/files/esources/petroleum/August2020/Fuel-Price-History.pdf",
        }
    )
    return sorted(urls, key=lambda u: (_year_from_url(u) or 0, u))


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=60, verify=False)
    except Exception:
        logger.exception("[dmre_za] download failed: %s", url)
        return None
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        logger.warning("[dmre_za] not a PDF: %s HTTP=%d", url, resp.status_code)
        return None
    return resp.content


def _extract_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[dmre_za] pdfplumber not installed")
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        logger.exception("[dmre_za] PDF parse failed")
        return ""


def _parse_year(text: str, url: str) -> int | None:
    m = _YEAR_RE.search(text)
    if m:
        return int(m.group(1))
    return _year_from_url(url)


def _extract_rows(text: str, year: int) -> list[dict]:
    rows: list[dict] = []
    normalized = re.sub(r"[|\t]", " ", text)
    normalized = re.sub(r" +", " ", normalized)
    row_re = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|July|Aug|Sep|Sept|Oct|Nov|Dec)\b\s+"
        r"((?:\d{3,4}(?:\.\d+)?\s+){6}\d{3,4}(?:\.\d+)?)",
        re.I,
    )
    for match in row_re.finditer(normalized):
        month = _MONTHS.get(match.group(1).lower())
        if month is None:
            continue
        obs_date = date(year, month, 1).isoformat()
        prices = [
            _parse_number(n) for n in re.findall(r"\d{3,4}(?:\.\d+)?", match.group(2))
        ]
        if len(prices) != len(_PRODUCT_COLUMNS) or any(p is None for p in prices):
            continue
        for (product, area), price in zip(_PRODUCT_COLUMNS, prices):
            rows.append(
                {
                    "observation_date": obs_date,
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "litre",
                    "subnational_area": area,
                }
            )
    return rows


def fetch_dmre_za(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for i, url in enumerate(_discover_pdfs(session)):
        if i > 0:
            time.sleep(_THROTTLE_S)
        url_year = _year_from_url(url)
        if url_year and date(url_year, 12, 31) <= cutoff:
            continue
        pdf_bytes = _download_pdf(session, url)
        if pdf_bytes is None:
            continue
        text = _extract_text(pdf_bytes)
        year = _parse_year(text, url)
        if year is None:
            logger.warning("[dmre_za] could not parse year for %s", url)
            continue
        parsed = [
            r
            for r in _extract_rows(text, year)
            if r["observation_date"] > cutoff.isoformat()
        ]
        rows.extend(parsed)
        logger.info("[dmre_za] %s → %d rows", year, len(parsed))
    if not rows:
        logger.info("[dmre_za] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(
            subset=["observation_date", "fuel_product", "subnational_area"]
        )
        .sort_values(["observation_date", "fuel_product", "subnational_area"])
        .reset_index(drop=True)
    )
    logger.info(
        "[dmre_za] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_dmre_za"]
