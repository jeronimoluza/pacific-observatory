"""Ghana NPA ex-pump price-floor PDFs."""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import date
from urllib.parse import unquote, urljoin

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://npa.gov.gh"
_UPLOADS = f"{_BASE_URL}/wp-content/uploads"
_COUNTRY = "Ghana"
_CURRENCY = "GHS"
_SOURCE_KEY = "npa_gh_price_floors"
_THROTTLE_S = 0.7

_PDF_HREF_RE = re.compile(
    r'href="([^"]+Ex-(?:Refinery-and-)?Pump-Price-Floors[^"]+\.pdf)"', re.I
)
_DATE_RANGE_RE = re.compile(
    r"(?:for-)?(\d{1,2})(?:st|nd|rd|th)?-(?:to-)?(\d{1,2})(?:st|nd|rd|th)?-([A-Za-z]+)-(\d{4})",
    re.I,
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
_PRODUCTS = {
    "petrol": "Petrol",
    "diesel": "Diesel",
    "kerosene": "Kerosene",
    "lpg": "LPG",
}


def _parse_number(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        val = float(raw.replace(",", "").strip())
    except ValueError:
        return None
    return val if val > 0 else None


def _date_from_filename(url: str) -> date | None:
    name = unquote(url.rsplit("/", 1)[-1]).replace("%E2%80%93", "-")
    name = name.replace("–", "-").replace("_", "-")
    m = _DATE_RANGE_RE.search(name)
    if not m:
        return None
    month = _MONTHS.get(m.group(3).lower())
    if not month:
        return None
    try:
        return date(int(m.group(4)), month, int(m.group(1)))
    except ValueError:
        return None


def _discover_pdfs(session, cutoff: date) -> list[tuple[date | None, str]]:
    out: dict[str, date | None] = {}
    today = date.today()
    for year in range(max(2024, cutoff.year), today.year + 1):
        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            url = f"{_UPLOADS}/{year}/{month:02d}/"
            try:
                resp = session.get(url, timeout=30)
            except Exception:
                logger.exception("[npa_gh] directory fetch failed: %s", url)
                continue
            if resp.status_code != 200:
                continue
            for href in _PDF_HREF_RE.findall(resp.text):
                pdf_url = urljoin(url, href)
                obs_date = _date_from_filename(pdf_url)
                if obs_date is None:
                    continue
                if obs_date <= cutoff:
                    continue
                out[pdf_url] = obs_date
            time.sleep(_THROTTLE_S)
    return sorted((d, u) for u, d in out.items())


def _extract_text(pdf_bytes: bytes) -> tuple[str, list[list[list[str | None]]]]:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[npa_gh] pdfplumber not installed")
        return "", []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
            tables = [page.extract_tables() or [] for page in pdf.pages]
            return text, tables
    except Exception:
        logger.exception("[npa_gh] PDF parse failed")
        return "", []


def _prices_from_tables(tables: list[list[list[str | None]]]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for page_tables in tables:
        for table in page_tables:
            for row in table or []:
                cells = [re.sub(r"\s+", " ", c or "").strip() for c in row or []]
                joined = " ".join(cells).lower()
                label = next(
                    (v for k, v in _PRODUCTS.items() if re.search(rf"\b{k}\b", joined)),
                    None,
                )
                if not label or label in prices:
                    continue
                nums = [
                    _parse_number(n)
                    for n in re.findall(r"\d+(?:\.\d+)?", " ".join(cells[1:]))
                ]
                nums = [n for n in nums if n is not None]
                if nums:
                    prices[label] = nums[-1]
    return prices


def _prices_from_text(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        low = line.lower()
        label = next(
            (v for k, v in _PRODUCTS.items() if re.search(rf"\b{k}\b", low)), None
        )
        if not label or label in prices:
            continue
        nums = [_parse_number(n) for n in re.findall(r"\d+(?:\.\d+)?", line)]
        nums = [n for n in nums if n is not None]
        if len(nums) >= 2:
            prices[label] = nums[-1]
    return prices


def _download(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=60)
    except Exception:
        logger.exception("[npa_gh] download failed: %s", url)
        return None
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        logger.warning("[npa_gh] not a PDF: %s HTTP=%d", url, resp.status_code)
        return None
    return resp.content


def fetch_npa_gh(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for obs_date, url in _discover_pdfs(session, cutoff):
        if obs_date is None or obs_date <= cutoff:
            continue
        pdf_bytes = _download(session, url)
        if pdf_bytes is None:
            continue
        text, tables = _extract_text(pdf_bytes)
        prices = _prices_from_tables(tables) or _prices_from_text(text)
        if not prices:
            logger.warning("[npa_gh] no prices parsed from %s", url)
            continue
        for product, price in prices.items():
            unit = "kilogram" if product == "LPG" else "litre"
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": unit,
                }
            )
        logger.info("[npa_gh] %s → %d products", obs_date, len(prices))
        time.sleep(_THROTTLE_S)
    if not rows:
        logger.info("[npa_gh] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[npa_gh] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_npa_gh"]
