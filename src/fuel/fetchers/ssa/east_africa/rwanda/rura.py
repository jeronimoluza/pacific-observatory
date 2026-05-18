"""RURA Rwanda regulated fuel pump-price tariff PDFs.

Rwanda Utilities Regulatory Authority publishes official tariff PDFs at
``https://www.rura.rw/publications/tariffs``. The current site exposes the
latest tariff document and older snapshots are available through the Wayback
CDX API. The fetcher discovers first-party RURA PDF links from the live and
archived tariff listings, extracts selectable PDF text with pdfplumber, and
falls back to Tesseract OCR in English when needed.
"""

from __future__ import annotations

import io
import logging
import re
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from PIL import Image

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.rura.rw"
_INDEX_URLS = [
    "https://www.rura.rw/publications/tariffs",
    "https://www.rura.rw/index.php?L=0&id=288",
    "https://rura.prod.risa.rw/publications/tariffs",
]
_CDX_URLS = [
    (
        "https://web.archive.org/cdx/search/cdx?"
        "url=www.rura.rw/publications/tariffs&output=json&"
        "fl=timestamp,statuscode&filter=statuscode:200"
    ),
    (
        "https://web.archive.org/cdx/search/cdx?"
        "url=www.rura.rw/index.php?L=0&id=288&output=json&"
        "fl=timestamp,statuscode&filter=statuscode:200"
    ),
]
_WAYBACK_FMT = "https://web.archive.org/web/{ts}id_/{url}"
_COUNTRY = "Rwanda"
_CURRENCY = "RWF"
_SOURCE_KEY = "rura_rw_monthly"
_THROTTLE_S = 1.0

_FUEL_TITLE_RE = re.compile(r"\b(fuel|pump|petroleum)\b.*\b(price|tariff)", re.I)
_DATE_RE = re.compile(
    r"(?:effective|effect)\s+(?:from|on)?\s*"
    r"([0-3]?\d)(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
    re.I,
)
_DATE_ALT_RE = re.compile(r"([0-3]?\d)(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})", re.I)
_PRODUCTS = [
    ("Petrol", re.compile(r"\b(?:petrol|gasoline)\b", re.I)),
    ("Diesel", re.compile(r"\bdiesel\b", re.I)),
    ("Kerosene", re.compile(r"\b(?:kerosene|illuminating\s+paraffin)\b", re.I)),
]
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


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 100 <= value <= 10000 else None


def _parse_date(text: str) -> date | None:
    for pattern in (_DATE_RE, _DATE_ALT_RE):
        match = pattern.search(text)
        if not match:
            continue
        month = _MONTHS.get(match.group(2).lower())
        if not month:
            continue
        try:
            return date(int(match.group(3)), month, int(match.group(1)))
        except ValueError:
            continue
    return None


def _discover_pdfs_from_html(html: str, page_url: str) -> dict[str, date | None]:
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, date | None] = {}
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.stripped_strings)
        href = urljoin(page_url, anchor["href"])
        haystack = f"{label} {href}"
        if not _FUEL_TITLE_RE.search(haystack):
            continue
        if ".pdf" not in href.lower() and "fileadmin" not in href.lower():
            continue
        out[href] = _parse_date(haystack)
    return out


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=45)
    except Exception:
        logger.exception("[rura_rw] HTML request failed: %s", url)
        return None
    if resp.status_code != 200:
        return None
    return resp.text


def _list_wayback_pages(session, url: str, cdx_url: str, cutoff: date) -> list[str]:
    from_ts = cutoff.strftime("%Y%m%d")
    to_ts = date.today().strftime("%Y%m%d")
    try:
        resp = session.get(f"{cdx_url}&from={from_ts}&to={to_ts}", timeout=60)
    except Exception:
        logger.exception("[rura_rw] CDX request failed")
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    return [_WAYBACK_FMT.format(ts=row[0], url=url) for row in data[1:]]


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=90)
    except Exception:
        logger.exception("[rura_rw] PDF request failed: %s", url)
        return None
    if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
        return resp.content
    return None


def _pdf_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""


def _image_to_text(image: Image.Image) -> str:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang="eng")
    except Exception:
        pass
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "page.png"
        out_base = Path(tmp) / "ocr"
        image.save(img_path)
        try:
            subprocess.run(
                ["tesseract", str(img_path), str(out_base), "-l", "eng"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return out_base.with_suffix(".txt").read_text(
                encoding="utf-8", errors="ignore"
            )
        except Exception:
            return ""


def _ocr_pdf(pdf_bytes: bytes) -> str:
    try:
        from pdf2image import convert_from_bytes

        return "\n".join(
            _image_to_text(img) for img in convert_from_bytes(pdf_bytes, dpi=220)
        )
    except Exception:
        logger.debug("[rura_rw] pdf2image unavailable; falling back to pdftoppm")
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "in.pdf"
        prefix = Path(tmp) / "page"
        pdf_path.write_bytes(pdf_bytes)
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-r",
                    "220",
                    "-png",
                    str(pdf_path),
                    str(prefix),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            logger.warning("[rura_rw] pdftoppm fallback failed: %s", exc)
            return ""
        pages = sorted(Path(tmp).glob("page-*.png"))
        return "\n".join(_image_to_text(Image.open(p)) for p in pages)


def _extract_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        for label, pattern in _PRODUCTS:
            if label in prices or not pattern.search(line):
                continue
            nums = [
                _parse_number(m.group(0))
                for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", line)
            ]
            vals = [n for n in nums if n is not None]
            if vals:
                prices[label] = vals[-1]
    return prices


def fetch_rura_rw(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    candidates: dict[str, date | None] = {}
    for url in _INDEX_URLS:
        html = _fetch_html(session, url)
        if html:
            candidates.update(_discover_pdfs_from_html(html, url))
    for url, cdx_url in zip(_INDEX_URLS[:2], _CDX_URLS):
        for wb_url in _list_wayback_pages(session, url, cdx_url, cutoff):
            time.sleep(_THROTTLE_S)
            html = _fetch_html(session, wb_url)
            if html:
                candidates.update(_discover_pdfs_from_html(html, wb_url))

    rows: list[dict] = []
    for pdf_url, link_date in sorted(candidates.items()):
        time.sleep(_THROTTLE_S)
        pdf_bytes = _download_pdf(session, pdf_url)
        if not pdf_bytes:
            continue
        text = _pdf_text(pdf_bytes)
        if not text.strip():
            text = _ocr_pdf(pdf_bytes)
        obs_date = _parse_date(text) or link_date or _parse_date(pdf_url)
        if obs_date is None or obs_date <= cutoff:
            continue
        prices = _extract_prices(text)
        if not prices:
            logger.warning("[rura_rw] no prices parsed from %s", pdf_url)
            continue
        for product, price in prices.items():
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                }
            )

    if not rows:
        logger.info("[rura_rw] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_rura_rw"]
