"""Collect Bahamas Wholesale Agencies' dated public product price list."""
from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash


logger = logging.getLogger(__name__)
_LISTING_URL = "https://www.bahamaswholesale.com/product-listing"
_SOURCE_KEY = "bahamas_bahamaswholesale"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_PDF_RE = re.compile(
    r'href="([^"]+\.pdf)"[^>]+aria-label="[^"]*product price list', re.IGNORECASE
)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_ROW_RE = re.compile(
    r"^(\d{3}-\d{4})\s+(.+?)\s+(\S+)\s+"
    r"(\d+(?:,\d{3})*\.\d{2})\s+(\d+(?:,\d{3})*\.\d{2})\s+([XTF])\s*$"
)


def _extract_rows(pdf_bytes: bytes, source_url: str) -> list[dict]:
    rows = []
    scrape_ts = get_scrape_ts()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        texts = [page.extract_text(layout=True) or "" for page in pdf.pages]
    date_match = _DATE_RE.search(texts[0] if texts else "")
    if not date_match:
        return rows
    observation_date = datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat()
    for text in texts:
        for line in text.splitlines():
            match = _ROW_RE.match(line.strip())
            if not match:
                continue
            item_code, description, unit, _pre_tax, vat_price, vat_code = match.groups()
            price = float(vat_price.replace(",", ""))
            if price <= 0:
                continue
            if unit.endswith("CS") and unit != "CS":
                prefix = unit[:-2]
                description = f"{description} {prefix}".strip()
                unit = "CS"
            row = {
                "observation_date": observation_date,
                "period_kind": "snapshot",
                "country": "Bahamas",
                "source_key": _SOURCE_KEY,
                "item_name": f"{item_code} - {description}",
                "price_local": price,
                "currency": "BSD",
                "unit": unit,
                "source_url": source_url,
                "notes": f"VAT code={vat_code}; price is listed w/VAT",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_bahamas_bahamaswholesale(cutoff: date):
    session = get_session()
    try:
        listing = session.get(_LISTING_URL, timeout=30)
        listing.raise_for_status()
        match = _PDF_RE.search(listing.text)
        if not match:
            logger.warning("[%s] product price-list PDF not found", _SOURCE_KEY)
            return None
        pdf_url = urljoin(_LISTING_URL, match.group(1))
        response = session.get(pdf_url, timeout=60)
        response.raise_for_status()
        rows = _extract_rows(response.content, pdf_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] collection failed: %s", _SOURCE_KEY, exc)
        return None
    rows = [row for row in rows if date.fromisoformat(row["observation_date"]) > cutoff]
    logger.info("[%s] produced %d post-cutoff rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
