"""Solomon Islands Electricity Authority (SIEA / Solomon Power) — electricity tariff.

Fetches the monthly "Charges for Supply of Electricity" PDF published at
solomonpower.com.sb via the WordPress media REST API. Emits one PriceObservation
per tariff tier (customer category × consumption block). Retail (Prepaid) rates only;
the Postpaid and Non-Regular sections are intentionally skipped — Prepaid is the
household-comparable rate for PPP purposes.

COICOP: 04.5.1 (electricity).
Base URL: https://solomonpower.com.sb/wp-json/wp/v2/media?search=charges
PDF pattern: /wp-content/uploads/YYYY/MM/{Month}-Charges.pdf
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_WP_MEDIA_URL = (
    "https://solomonpower.com.sb/wp-json/wp/v2/media"
    "?search=charges&per_page=24&_fields=source_url,title,date&orderby=date&order=desc"
)
_COUNTRY = "Solomon Islands"
_CURRENCY = "SBD"
_SOURCE_KEY = "sb_siea_tariff"
_SOURCE_URL = "https://solomonpower.com.sb/tariff/"
_COICOP_CODE = "04.5.1"
_UNIT = "kWh"
_IDENT = ["source_key", "observation_date", "item_name"]

_CATEGORY_RE = re.compile(
    r"(Domestic|Commercial|Industrial)\s+(<\s*\d+|[\d,]+\s*-\s*[\d,]+|>\s*\d+|All)\s+kWh"
    r".*?"
    r"([\d.]+)\s+([\d.]+)\s+([\d.]+)",
    re.DOTALL,
)
_EFFECTIVE_DATE_RE = re.compile(r"EFFECTIVE\s+(\d+\s+\w+\s+\d{4})", re.IGNORECASE)


def _parse_effective_date(text: str) -> date | None:
    m = _EFFECTIVE_DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).strip(), "%d %B %Y").date()
    except ValueError:
        return None


def _parse_prepaid_rows(text: str, obs_date: date, source_url: str) -> list[dict]:
    rows: list[dict] = []
    prepaid_start = text.find("Prepaid Customers")
    postpaid_start = text.find("Postpaid Customers")
    if prepaid_start == -1:
        logger.warning("[%s] 'Prepaid Customers' section not found", _SOURCE_KEY)
        return rows
    section_end = postpaid_start if postpaid_start > prepaid_start else len(text)
    section = text[prepaid_start:section_end]

    for m in _CATEGORY_RE.finditer(section):
        category = m.group(1)
        block = m.group(2).strip().replace(" ", "")
        non_fuel = float(m.group(3))
        fuel = float(m.group(4))
        total = float(m.group(5))
        item_name = f"Electricity, {category.lower()}, {block} kWh block, prepaid"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": round(total, 4),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": source_url,
            "notes": f"non_fuel={non_fuel} SBD/kWh; fuel={fuel} SBD/kWh",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_sb_siea_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_WP_MEDIA_URL, timeout=30)
    resp.raise_for_status()
    media_items = resp.json()

    rows: list[dict] = []
    for item in media_items:
        raw_date = item.get("date", "")
        try:
            pub_date = datetime.fromisoformat(raw_date).date()
        except (ValueError, TypeError):
            continue
        if pub_date <= cutoff:
            continue
        pdf_url = item.get("source_url", "")
        if not pdf_url.endswith(".pdf"):
            continue
        pdf_resp = session.get(pdf_url, timeout=60)
        if pdf_resp.status_code != 200:
            logger.warning(
                "[%s] PDF fetch failed (%d): %s",
                _SOURCE_KEY,
                pdf_resp.status_code,
                pdf_url,
            )
            continue
        try:
            with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:
            logger.warning(
                "[%s] pdfplumber error for %s: %s", _SOURCE_KEY, pdf_url, exc
            )
            continue
        obs_date = _parse_effective_date(text)
        if obs_date is None:
            obs_date = pub_date
        batch = _parse_prepaid_rows(text, obs_date, pdf_url)
        if not batch:
            logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, pdf_url)
        rows.extend(batch)

    return pd.DataFrame(rows) if rows else None
