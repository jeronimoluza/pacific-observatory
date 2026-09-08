"""Philippines Department of Energy (DOE) — weekly NCR retail pump-price bulletin.

The "NCR Pump Prices" tab of doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices
links one PDF per week (hosted on the department's Nuxeo-style CMS at
prod-cms.doe.gov.ph/documents/d/guest/ncr-price-monitoring-<MMDDYYYY>-pdf,
served with no auth). The PDF is a per-city, per-brand price-survey table
(PETRON/SHELL/CALTEX/PHOENIX/TOTAL/FLYING V/UNIOIL/SEAOIL/PTT/INDEPENDENT
columns) for RON 100/97/95/91 petrol grades plus DIESEL/DIESEL PLUS/KEROSENE,
with an "OVERALL RANGE" and "COMMON PRICE" column per (area, product) row.

Column-level brand cells span multiple product rows in the PDF's underlying
table structure, which defeats pdfplumber's cell extraction — the reliable
signal is the trailing "<low> - <high> <common>" triplet that
``page.extract_text()`` keeps on one line per (area, product) row. This
fetcher parses that triplet and emits the COMMON PRICE only when the survey
found consensus (the source itself writes "#N/A" when brands disagree too
widely to average — those rows are dropped, not fabricated).

Only the NCR (National Capital Region) tab is scraped in this first pass;
North/South Luzon, Visayas and Mindanao tabs exist on the same site and are
a natural follow-up (same PDF shape, different filename prefix).

Source URL: https://doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices/ncr-pump-prices
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd
import pdfplumber
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://doe.gov.ph/data-and-prices/liquid-fuels/retail-pump-prices/ncr-pump-prices"
_COUNTRY = "Philippines"
_CURRENCY = "PHP"
_SOURCE_KEY = "doe_ncr_pump_prices"
_IDENT = ["source_key", "observation_date", "item_name"]
_HEADERS = {"User-Agent": "pacific-observatory/prices (+research)"}

_PDF_HREF_RE = re.compile(
    r'href="(https://prod-cms\.doe\.gov\.ph/documents/d/guest/ncr-price-monitoring-(\d{8})-pdf)"'
)
_ROW_RE = re.compile(
    r"^(?:([A-Za-z][A-Za-z .]+?)\s+)?"
    r"(RON\s?\d+|DIESEL PLUS|DIESEL|KEROSENE)\s.*?"
    r"([0-9.]+)\s*-\s*([0-9.]+)\s+([0-9.]+|#N/A)\s*$"
)

_KNOWN_NCR_AREAS = {
    "caloocan", "las pinas", "las piñas", "makati", "malabon", "mandaluyong",
    "manila", "marikina", "muntinlupa", "navotas", "paranaque", "parañaque",
    "pasay", "pasig", "quezon", "san juan", "taguig", "valenzuela", "pateros",
}


def _is_known_area(area: str) -> bool:
    """Guards against a source-side PDF defect: two city labels positioned
    at the same coordinates get interleaved character-by-character by
    pdfplumber's text extraction (confirmed live: "Mandaluyong City" and
    "Muntinlupa City" merged into "MCuanlotioncluapna C Citiyty"). Rather
    than emit a garbled city name, drop rows whose area doesn't match a
    known NCR city/municipality."""
    key = area.lower().replace("city", "").replace("cty", "").strip()
    return key in _KNOWN_NCR_AREAS


_PRODUCT_COICOP = {
    "DIESEL": "07.2.2.1",
    "DIESEL PLUS": "07.2.2.1",
    "KEROSENE": "07.2.2.3",
}


def _coicop_for(product: str) -> str:
    if product in _PRODUCT_COICOP:
        return _PRODUCT_COICOP[product]
    return "07.2.2.2"  # RON <n> petrol grades


def _latest_pdf_url() -> tuple[str, date] | None:
    resp = requests.get(_LISTING_URL, headers=_HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for listing page", _SOURCE_KEY, resp.status_code)
        return None
    candidates = []
    for url, mmddyyyy in _PDF_HREF_RE.findall(resp.text):
        try:
            d = datetime.strptime(mmddyyyy, "%m%d%Y").date()
        except ValueError:
            continue
        candidates.append((d, url))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    d, url = candidates[-1]
    return url, d


def _parse_pdf(content: bytes) -> list[dict]:
    text = ""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for p in pdf.pages:
            text += (p.extract_text() or "") + "\n"

    rows: list[dict] = []
    current_area = None
    for line in text.split("\n"):
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        area, product, low, high, common = m.groups()
        if area:
            current_area = area.strip()
        if not current_area or common == "#N/A":
            continue
        if not _is_known_area(current_area):
            continue
        rows.append(
            {
                "area": current_area,
                "product": product.strip(),
                "common_price": float(common),
            }
        )
    return rows


def fetch_doe_ncr_pump_prices(cutoff: date) -> pd.DataFrame | None:
    found = _latest_pdf_url()
    if not found:
        logger.warning("[%s] could not locate any NCR pump-price PDF", _SOURCE_KEY)
        return None
    pdf_url, week_start = found
    if week_start <= cutoff:
        return None

    resp = requests.get(pdf_url, headers=_HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d downloading %s", _SOURCE_KEY, resp.status_code, pdf_url)
        return None

    parsed = _parse_pdf(resp.content)
    if not parsed:
        logger.warning("[%s] No rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    rows: list[dict] = []
    for r in parsed:
        row = {
            "observation_date": week_start.isoformat(),
            "period_kind": "weekly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _coicop_for(r["product"]),
            "item_name": f"DOE NCR retail pump price, {r['area']}, {r['product']}",
            "price_local": r["common_price"],
            "currency": _CURRENCY,
            "unit": "L",
            "city": r["area"],
            "source_url": pdf_url,
            "notes": "COMMON PRICE across surveyed brands (source-published consensus)",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning("[%s] %d duplicate observation_hash rows before de-dup", _SOURCE_KEY, dup_count)
        df = df.drop_duplicates(subset="observation_hash")
    return df
