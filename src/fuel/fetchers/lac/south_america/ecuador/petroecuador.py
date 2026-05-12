"""Ecuador EP Petroecuador monthly terminal-price fetcher.

Source: EP Petroecuador, "Histórico de precios a nivel de terminal".
Listing: https://www.eppetroecuador.ec/?p=20421

Petroecuador publishes a monthly "ESTRUCTURA DE PRECIOS" PDF setting
terminal (wholesale) prices that authorized distributors pay. These are
state-set prices anchored to executive decrees and apply for a roughly
month-long vigencia period (e.g. "DEL 12 DE DICIEMBRE DE 2024 AL 11 DE
ENERO DE 2025").

The listing page is an HTML calendar table; each Año/Mes cell links
either to a /wp-content/uploads/YYYY/MM/ESTRUCTURA-DE-PRECIOS-<MES>-<YYYY>.pdf
or a /wp-content/plugins/download-monitor/download.php?id=NNNN wrapper.
Some months have revision suffixes ("Mayo (3)", "Junio (2)") indicating
mid-period price changes — both variants are followed.

Prices are reported in USD per Galón / Kilogramo / Millón de BTUs.
"""

from __future__ import annotations

import io
import logging
import re
import time
import unicodedata
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.eppetroecuador.ec/?p=20421"
_REQUEST_DELAY_S = 1.2

_COUNTRY = "Ecuador"
_CURRENCY = "USD"
_SOURCE_KEY = "ec_petroecuador_monthly"

_MONTH_NAMES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_VIGENCIA_RE = re.compile(
    r"DEL\s+(\d{1,2})\s+(?:DE\s+)?([A-ZÁÉÍÓÚÑ]+)"
    r"(?:\s+(?:DE\s+)?(\d{4}))?"
    r"\s+AL\s+\d{1,2}\s+(?:DE\s+)?[A-ZÁÉÍÓÚÑ]+\s+(?:DE\s+)?(\d{4})",
    re.IGNORECASE,
)
# Older single-month form: "DEL 01 AL 30 DE SEPTIEMBRE DE 2018" or "01 AL 31 DE MAYO 2018"
_VIGENCIA_SINGLE_RE = re.compile(
    r"(?:DEL\s+)?(\d{1,2})\s+AL\s+\d{1,2}\s+(?:DE\s+)?([A-ZÁÉÍÓÚÑ]+)\s+(?:DE\s+)?(\d{4})",
    re.IGNORECASE,
)
# Earliest form: "PERIODO DE VIGENCIA: ENERO 2018" / "OCTUBRE DE 2019" — month + year only.
_VIGENCIA_MONTH_ONLY_RE = re.compile(
    r"PERIODO\s+DE\s+VIGENCIA[:\s]+([A-ZÁÉÍÓÚÑ]+)\s+(?:DE\s+)?(\d{4})",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"\$\s*-?\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2,6})")
_UNIT_TOKENS = ("Galones", "Galón", "Kilogramos", "Kilogramo", "Millón de BTUs")

# Products to extract. Other rows are skipped. Sector suffix is kept so
# downstream filtering (carry_forward, retail vs subsidized) can stay
# in the YAML config.
_PRODUCT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("GASOLINA EXTRA", re.compile(r"^GASOLINA\s+EXTRA\s+PETROLERO\b", re.IGNORECASE)),
    (
        "GASOLINA SUPER PREMIUM 95",
        re.compile(r"^GASOLINA\s+SUPER\s+PREMIUM\s+95\s+PETROLERO\b", re.IGNORECASE),
    ),
    (
        "EXTRA CON ETANOL",
        re.compile(r"^EXTRA\s+CON\s+ETANOL\s+PETROLERO\b", re.IGNORECASE),
    ),
    ("DIESEL 2", re.compile(r"^DIESEL\s+2\s+PETROLERO\b", re.IGNORECASE)),
    ("DIESEL PREMIUM", re.compile(r"^DIESEL\s+PREMIUM\s+PETROLERO\b", re.IGNORECASE)),
    ("DIESEL 1", re.compile(r"^DIESEL\s+1\s+PETROLERO\b", re.IGNORECASE)),
    ("FUEL OIL", re.compile(r"^FUEL\s+OIL\s+PETROLERO\b", re.IGNORECASE)),
    (
        "GLP DOMESTICO",
        re.compile(
            r"^GAS\s+LICUADO\s+DE\s+PETR[OÓ]LEO\s+\(G\.?L\.?P\.?\)\s+DOM", re.IGNORECASE
        ),
    ),
    (
        "GLP INDUSTRIAL",
        re.compile(
            r"^GAS\s+LICUADO\s+DE\s+PETR[OÓ]LEO\s+\(GLP\)\s+INDUSTRIAL", re.IGNORECASE
        ),
    ),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _parse_listing(html: str, base_url: str) -> list[str]:
    """Return PDF URLs from the calendar table, ordered top→bottom (newest first)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for a in table.find_all("a", href=True):
        href = a["href"].strip()
        # Normalize to https.
        if href.startswith("http://www.eppetroecuador.ec"):
            href = (
                "https://www.eppetroecuador.ec"
                + href[len("http://www.eppetroecuador.ec") :]
            )
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
    return urls


def _parse_vigencia(text: str) -> date | None:
    """Extract the first day of the vigencia period.

    Two formats observed:
      "DEL 12 DE DICIEMBRE DE 2024 AL 11 DE ENERO DE 2025"  (year on both sides)
      "DEL 12 DE ENERO AL 11 DE FEBRERO DE 2024"            (year only on end)
    """
    m = _VIGENCIA_RE.search(text)
    if m:
        day = int(m.group(1))
        mes = _strip_accents(m.group(2)).lower()
        end_year = int(m.group(4))
        start_year = int(m.group(3)) if m.group(3) else end_year
        month = _MONTH_NAMES.get(mes)
        if month is None:
            return None
        # If only end-year is given and we cross Dec→Jan, start_year is end_year - 1.
        if not m.group(3) and month == 12:
            start_year = end_year - 1
        try:
            return date(start_year, month, day)
        except ValueError:
            return None
    m2 = _VIGENCIA_SINGLE_RE.search(text)
    if m2:
        day = int(m2.group(1))
        mes = _strip_accents(m2.group(2)).lower()
        year = int(m2.group(3))
        month = _MONTH_NAMES.get(mes)
        if month is None:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None
    m3 = _VIGENCIA_MONTH_ONLY_RE.search(text)
    if m3:
        mes = _strip_accents(m3.group(1)).lower()
        year = int(m3.group(2))
        month = _MONTH_NAMES.get(mes)
        if month is None:
            return None
        try:
            return date(year, month, 1)
        except ValueError:
            return None
    return None


def _match_product(line: str) -> str | None:
    norm = _normalize(line)
    for canonical, pattern in _PRODUCT_PATTERNS:
        if pattern.match(norm):
            return canonical
    return None


def _extract_unit(line: str) -> str:
    norm_lower = _normalize(line).lower()
    if "kilogramos" in norm_lower or "kilogramo" in norm_lower:
        return "kg"
    if "mill" in norm_lower and "btu" in norm_lower:
        return "mmbtu"
    return "gal"


def _parse_pdf(pdf_bytes: bytes) -> tuple[date | None, list[tuple[str, str, float]]]:
    """Return (effective_date, [(product, unit, price), ...]) from one PDF."""
    out: list[tuple[str, str, float]] = []
    eff_date: date | None = None
    seen_products: set[str] = set()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text_parts: list[str] = []
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            full_text_parts.append(page_text)
        text = "\n".join(full_text_parts)

    if eff_date is None:
        eff_date = _parse_vigencia(text)

    for line in text.splitlines():
        product = _match_product(line)
        if product is None or product in seen_products:
            continue
        prices = _PRICE_RE.findall(line)
        if not prices:
            continue
        # Standardize "2,748243" → "2.748243"
        raw = (
            prices[0].replace(".", "").replace(",", ".")
            if prices[0].count(",") == 1 and "." in prices[0]
            else prices[0].replace(",", ".")
        )
        try:
            price = float(raw)
        except ValueError:
            continue
        if price <= 0:
            continue
        unit = _extract_unit(line)
        out.append((product, unit, price))
        seen_products.add(product)
    return eff_date, out


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=60, allow_redirects=True)
        if resp.status_code != 200:
            return None
        ctype = resp.headers.get("Content-Type", "").lower()
        if "pdf" not in ctype and not resp.content.startswith(b"%PDF"):
            return None
        return resp.content
    except Exception:
        return None


def fetch_ec_petroecuador(cutoff: date) -> pd.DataFrame | None:
    """Fetch Ecuador Petroecuador monthly terminal prices (USD per gal/kg/mmbtu)."""
    session = make_session()
    try:
        resp = session.get(_LISTING_URL, timeout=45)
        resp.raise_for_status()
    except Exception:
        logger.exception("[ec_petroecuador] Failed to fetch listing page")
        return None

    pdf_urls = _parse_listing(resp.text, _LISTING_URL)
    if not pdf_urls:
        logger.warning("[ec_petroecuador] No PDFs on listing page")
        return None

    seen_keys: set[tuple[str, str]] = set()
    rows: list[dict] = []

    for url in pdf_urls:
        pdf_bytes = _download_pdf(session, url)
        time.sleep(_REQUEST_DELAY_S)
        if pdf_bytes is None:
            logger.warning("[ec_petroecuador] Could not download %s", url)
            continue
        eff_date, products = _parse_pdf(pdf_bytes)
        if eff_date is None or not products:
            logger.warning("[ec_petroecuador] Could not parse %s", url)
            continue
        if eff_date <= cutoff:
            continue
        date_str = eff_date.strftime("%Y-%m-%d")
        added = 0
        for product, unit, price in products:
            key = (date_str, product)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            rows.append(
                {
                    "observation_date": date_str,
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 6),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": unit,
                }
            )
            added += 1
        logger.info("[ec_petroecuador] %s → %d products", eff_date, added)

    if not rows:
        logger.info("[ec_petroecuador] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[ec_petroecuador] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
