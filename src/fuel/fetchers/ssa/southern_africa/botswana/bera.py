"""BERA Botswana official petroleum-price gazettes and press releases.

Botswana Energy Regulatory Authority publishes petroleum press releases and
official Control of Goods petroleum-price gazette PDFs at
``https://www.bera.co.bw/petroleum.php`` and the media listing. Gazette
schedule tables provide absolute location prices in thebe per litre; this
fetcher uses the Gaborone row as the country reference. Press releases that
publish only product deltas are accumulated from the latest official absolute
gazette anchor.
"""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.bera.co.bw"
_INDEX_URLS = [
    f"{_BASE_URL}/petroleum.php",
    f"{_BASE_URL}/media.php",
]
_COUNTRY = "Botswana"
_CURRENCY = "BWP"
_SOURCE_KEY = "bera_bw_monthly"
_THROTTLE_S = 1.0

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_DATE_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z.]+)\s*,?\s+(\d{4})", re.I)
_NUM_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)
_FUEL_LINK_RE = re.compile(
    r"(fuel\s+prices?\s+adjust|petroleum\s+prices?.*regulations|"
    r"current\s+pump\s+prices|fuel\s+adjustment)",
    re.I,
)
_PRODUCT_ALIASES = [
    ("ULP 93", re.compile(r"\b(?:ULP\s*93|unleaded\s+petrol\s+93)\b", re.I)),
    ("ULP 95", re.compile(r"\b(?:ULP\s*95|unleaded\s+petrol\s+95)\b", re.I)),
    ("Diesel 50ppm", re.compile(r"\b(?:diesel\s+50\s*ppm|50\s*PPM|diesel)\b", re.I)),
    ("Diesel 500ppm", re.compile(r"\b(?:diesel\s+500\s*ppm|500\s*PPM)\b", re.I)),
    (
        "Illuminating Paraffin",
        re.compile(r"\b(?:illuminating\s+paraffin|paraffin|IK)\b", re.I),
    ),
]
_HEADER_MAP = {
    "ULP93": "ULP 93",
    "ULP": "ULP 95",
    "ULP95": "ULP 95",
    "50PPM": "Diesel 50ppm",
    "500PPM": "Diesel 500ppm",
    "IK": "Illuminating Paraffin",
}


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw.replace(",", "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_date(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if match:
        month = _MONTHS.get(match.group(2).lower().rstrip("."))
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                pass
    match = _NUM_DATE_RE.search(text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
    return None


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=45)
    except Exception:
        logger.exception("[bera_bw] index request failed: %s", url)
        return None
    if resp.status_code != 200:
        return None
    return resp.text


def _discover_pdfs(session) -> dict[str, date | None]:
    found: dict[str, date | None] = {}
    for url in _INDEX_URLS:
        html = _fetch_html(session, url)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(url, anchor["href"])
            label = " ".join(anchor.stripped_strings)
            parent = anchor.find_parent()
            context = parent.get_text(" ", strip=True) if parent else label
            haystack = f"{label} {context} {href}"
            if not _PDF_RE.search(href) or not _FUEL_LINK_RE.search(haystack):
                continue
            found[href] = _parse_date(haystack)
    return found


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=90)
    except Exception:
        logger.exception("[bera_bw] PDF request failed: %s", url)
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


def _normalize_header_token(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper()


def _extract_gaborone_prices(text: str) -> dict[str, float]:
    compact = re.sub(r"[ \t]+", " ", text)
    header = re.search(
        r"ULP\s*93\s+ULP\s*95\s+(?:50PPM|500PPM|Diesel).*?\bIK\b", compact, re.I
    )
    row = re.search(r"\bGaborone\s+((?:\d{3,5}\s+){2,5}\d{3,5})\b", compact, re.I)
    if not header or not row:
        return {}
    header_tokens = [
        _normalize_header_token(token)
        for token in re.findall(
            r"ULP\s*93|ULP\s*95|50PPM|500PPM|IK", header.group(0), re.I
        )
    ]
    nums = [int(n) for n in re.findall(r"\d{3,5}", row.group(1))]
    prices: dict[str, float] = {}
    for token, raw_value in zip(header_tokens, nums):
        product = _HEADER_MAP.get(token)
        if product:
            prices[product] = round(raw_value / 100.0, 4)
    return prices


def _extract_absolute_sentence_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        for product, pattern in _PRODUCT_ALIASES:
            if product in prices or not pattern.search(line):
                continue
            match = re.search(r"(?:P|BWP|pula)\s*([0-9]+(?:\.[0-9]+)?)", line, re.I)
            if not match:
                continue
            value = _parse_number(match.group(1))
            if value is not None:
                prices[product] = value
    return prices


def _extract_deltas(text: str) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for raw_line in text.splitlines():
        clauses = re.split(r";|\band\b|\bi{1,4}\)", re.sub(r"\s+", " ", raw_line))
        for clause in clauses:
            line = clause.strip()
            if not line:
                continue
            direction = 1.0 if re.search(r"\bincrease(?:d)?\b", line, re.I) else -1.0
            if not re.search(r"\b(?:increase(?:d)?|decrease(?:d)?)\b", line, re.I):
                continue
            amount = re.search(r"(\d+(?:\.\d+)?)\s*thebe", line, re.I)
            if not amount:
                continue
            delta = direction * float(amount.group(1)) / 100.0
            for product, pattern in _PRODUCT_ALIASES:
                if product in deltas or not pattern.search(line):
                    continue
                if product == "Diesel 500ppm" and "500" not in line:
                    continue
                if product == "Diesel 50ppm" and "500" in line:
                    continue
                deltas[product] = delta
    return deltas


def fetch_bera_bw(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    docs: list[tuple[date, str, dict[str, float], dict[str, float]]] = []
    for pdf_url, link_date in _discover_pdfs(session).items():
        time.sleep(_THROTTLE_S)
        pdf_bytes = _download_pdf(session, pdf_url)
        if not pdf_bytes:
            continue
        text = _pdf_text(pdf_bytes)
        obs_date = (
            (
                re.search(
                    r"(?:come into force|effect from|take effect)[^\n.]{0,80}",
                    text,
                    re.I,
                )
                and _parse_date(
                    re.search(
                        r"(?:come into force|effect from|take effect)[^\n.]{0,80}",
                        text,
                        re.I,
                    ).group(0)
                )
            )
            or link_date
            or _parse_date(text)
            or _parse_date(pdf_url)
        )
        if obs_date is None:
            continue
        absolute = _extract_gaborone_prices(text) or _extract_absolute_sentence_prices(
            text
        )
        deltas = _extract_deltas(text)
        if absolute or deltas:
            docs.append((obs_date, pdf_url, absolute, deltas))

    levels: dict[str, float] = {}
    rows: list[dict] = []
    for obs_date, _pdf_url, absolute, deltas in sorted(docs, key=lambda item: item[0]):
        if absolute:
            levels.update(absolute)
        elif deltas and levels:
            for product, delta in deltas.items():
                if product in levels:
                    levels[product] = round(levels[product] + delta, 4)
                elif product == "Diesel 50ppm" and "Diesel 500ppm" in levels:
                    levels[product] = round(levels["Diesel 500ppm"] + delta, 4)
        else:
            continue
        if obs_date <= cutoff:
            continue
        for product, price in levels.items():
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
        logger.info("[bera_bw] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_bera_bw"]
