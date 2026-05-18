"""Nicaragua INE weekly fuel price fetcher.

Source: Instituto Nicaragüense de Energía — Dirección General de Hidrocarburos.
Parent index: https://www.ine.gob.ni/?page_id=108819
Per-year combustibles indexes (?page_id=...):
  2026 → 129076,  2025 → 126710,  2024 → 124164,
  2023 → 116768,  2022 → 109029,  2021 → 109229.

The "Hidrocarburos" page uses a Divi DNXTE thumbs gallery whose tile click
URLs live in inline JS (`var et_link_options_data`) rather than as `<a href>`.
Each year sub-page exposes its weekly PDF URLs the same way.

Each weekly PDF ("MONITOREO DE PRECIOS DE LOS COMBUSTIBLES") opens with a
4-row comparison table:

  PRODUCTOS    PRECIO PROMEDIO (C$/L)        ...
               ACTUAL          ANTERIOR
               <DD MES YYYY>   <DD MES YYYY>
  GAS. REGULAR 47,82           47,82
  GAS. SÚPER   49,00           49,00
  DIESEL       43,22           43,22
  KEROSENE     56,87           59,17

The header "Realizado en la ciudad de Managua el DD de MES de YYYY" (or, in
older PDFs, "MONITOREO DE PRECIOS DEL DD DE MES DE YYYY") gives the canonical
observation date. NIO/L (C$/L).

Prices are establised weekly by distributors and are explicitly "no regulados
por el Estado"; we mark this market regime (carry_forward=false) at the YAML
config level.
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from datetime import date

import pandas as pd
import pdfplumber
import urllib3

from core.http import make_session

# INE's TLS chain misses an intermediate; disable the warning and fall back
# to verify=False (consistent with Panama Acodeco and Bangladesh BPC).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_PARENT_PAGE = "https://www.ine.gob.ni/?page_id=108819"
_YEAR_INDEX_PAGES = {
    2026: "https://www.ine.gob.ni/?page_id=129076",
    2025: "https://www.ine.gob.ni/?page_id=126710",
    2024: "https://www.ine.gob.ni/?page_id=124164",
    2023: "https://www.ine.gob.ni/?page_id=116768",
    2022: "https://www.ine.gob.ni/?page_id=109029",
    2021: "https://www.ine.gob.ni/?page_id=109229",
}
_REQUEST_DELAY_S = 0.6

_COUNTRY = "Nicaragua"
_CURRENCY = "NIO"
_SOURCE_KEY = "ni_ine_weekly"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-NI,es;q=0.9,en;q=0.8",
}

_LINK_OPTIONS_RE = re.compile(r"var\s+et_link_options_data\s*=\s*(\[.*?\]);", re.DOTALL)

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

# "Realizado en la ciudad de Managua el 06 de diciembre de 2021" — newer style.
_DATE_RE_REALIZADO = re.compile(
    r"Realizado\s+en\s+la\s+ciudad\s+de\s+Managua\s+el\s+"
    r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]+)\s+de(?:\s*l)?\s*(\d{4})",
    re.IGNORECASE,
)
# "MONITOREO DE PRECIOS DEL 04 DE ENERO DE 2021" — older style.
_DATE_RE_TITLE = re.compile(
    r"MONITOREO\s+DE\s+PRECIOS\s+DEL\s+"
    r"(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÑ]+)\s+DE\s+(\d{4})",
    re.IGNORECASE,
)

# Product lines: "GAS. REGULAR  47,82  47,82 ...". Captures the ACTUAL value.
_PRODUCT_RE = re.compile(
    r"^(GAS\.\s+REGULAR|GAS\.\s+S[ÚU]PER|DIESEL|DI[ÉE]SEL|KEROSENE)\s+"
    r"(\d+(?:[.,]\d+)?)\s+\d+(?:[.,]\d+)?",
    re.IGNORECASE | re.MULTILINE,
)

# Canonical product names emitted to CSV.
_CANONICAL = {
    "GAS. REGULAR": "Gasolina Regular",
    "GAS. SUPER": "Gasolina Súper",
    "GAS. SÚPER": "Gasolina Súper",
    "DIESEL": "Diésel",
    "DIÉSEL": "Diésel",
    "KEROSENE": "Kerosene",
}


def _extract_pdf_urls(html: str) -> list[str]:
    """Pull PDF URLs from the Divi gallery click-target JSON in inline JS."""
    m = _LINK_OPTIONS_RE.search(html)
    if not m:
        return []
    try:
        entries = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        url = entry.get("url", "")
        cls = entry.get("class", "")
        if not url.lower().endswith(".pdf"):
            continue
        if "thumbs_gallery_child" not in cls:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _parse_observation_date(text: str) -> date | None:
    m = _DATE_RE_REALIZADO.search(text)
    if not m:
        m = _DATE_RE_TITLE.search(text)
    if not m:
        return None
    month_key = m.group(2).lower()
    # Strip accents from any month token (e.g., "octubre" stays; legacy
    # files only use unaccented Spanish month names).
    month = _MONTH_NAMES.get(month_key)
    if month is None:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _parse_products(text: str) -> dict[str, float]:
    """Return {canonical_product: price_local} from a PDF page-1 text."""
    out: dict[str, float] = {}
    for m in _PRODUCT_RE.finditer(text):
        raw_product = re.sub(r"\s+", " ", m.group(1).upper().strip())
        canon = _CANONICAL.get(raw_product)
        if canon is None:
            continue
        try:
            price = float(m.group(2).replace(",", "."))
        except ValueError:
            continue
        if price <= 0:
            continue
        out.setdefault(canon, price)
    return out


def _parse_weekly_pdf(pdf_bytes: bytes) -> tuple[date | None, dict[str, float]]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() if pdf.pages else ""
    text = text or ""
    obs_date = _parse_observation_date(text)
    products = _parse_products(text)
    return obs_date, products


def fetch_ni_ine(cutoff: date) -> pd.DataFrame | None:
    """Fetch Nicaragua INE weekly Managua avg combustible prices (NIO/L)."""
    session = make_session(**_HEADERS)

    pdf_urls: list[str] = []
    seen: set[str] = set()
    for year, page_url in _YEAR_INDEX_PAGES.items():
        if year < cutoff.year:
            continue
        try:
            r = session.get(page_url, timeout=45, verify=False)
            r.raise_for_status()
        except Exception:
            logger.warning("[ni_ine] Failed to fetch year index %s", page_url)
            continue
        urls = _extract_pdf_urls(r.text)
        new = [u for u in urls if u not in seen]
        seen.update(new)
        pdf_urls.extend(new)
        logger.info("[ni_ine] year=%d index → %d PDFs", year, len(urls))
        time.sleep(_REQUEST_DELAY_S)

    if not pdf_urls:
        logger.warning("[ni_ine] No PDF URLs discovered across year indexes")
        return None

    rows: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    for url in pdf_urls:
        try:
            r = session.get(url, timeout=60, verify=False)
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                logger.warning("[ni_ine] Non-PDF for %s", url)
                time.sleep(_REQUEST_DELAY_S)
                continue
        except Exception:
            logger.warning("[ni_ine] Download failed: %s", url)
            time.sleep(_REQUEST_DELAY_S)
            continue
        try:
            obs_date, products = _parse_weekly_pdf(r.content)
        except Exception:
            logger.exception("[ni_ine] Parse failed for %s", url)
            time.sleep(_REQUEST_DELAY_S)
            continue
        time.sleep(_REQUEST_DELAY_S)
        if obs_date is None or not products:
            logger.warning("[ni_ine] No date or products in %s", url)
            continue
        if obs_date <= cutoff:
            continue
        date_str = obs_date.strftime("%Y-%m-%d")
        for product, price in products.items():
            key = (date_str, product)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            rows.append(
                {
                    "observation_date": date_str,
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )

    if not rows:
        logger.info("[ni_ine] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[ni_ine] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
