"""American Samoa Dept of Commerce (doc.as.gov), Statistics & Analysis Division
-- Basic Food Index (BFI), a monthly rapid-assessment news release tracking
~20 basic food items across 14 major-to-mid-size retail stores in the
territory.

The doc.as.gov site is a Wix site. The /stats page renders its "Basic Food
Index" tab client-side via the Wix FAQ widget (`_api/faq-server/v2/...`),
which needs a bearer token. The token is NOT a secret -- it is a
per-visitor-session instance token handed out by the unauthenticated
`_api/v1/access-tokens` endpoint (same pattern any anonymous site visitor's
browser gets), scoped to the FAQ app (appDefId
14c92d28-031e-7910-c9a8-a670011e062d). Verified live 2026-08-11:
  1. GET  /_api/v1/access-tokens                 -> apps[appDefId].accessToken
  2. POST /_api/faq-server/v2/question-entries/query
       {"query":{"cursorPaging":{"limit":50},
                 "filter":{"categoryId": <BFI category id>},
                 "sort":[{"fieldName":"sortOrder","order":"ASC"}]},
        "contentFormat":"DRAFTJS"}
       with header Authorization: <accessToken>
The BFI category groups one "question entry" per YEAR (e.g. "BFI - 2024"),
whose `draftjs` rich-text field embeds one link per MONTH ("BFI Press
Release for <Month> <Year>" -> PDF url). The category id is looked up by
title via `_api/faq-server/v2/categories` each run (resilient to the
category being deleted/recreated with a new id; falls back to the id
observed live if the title-lookup ever comes back empty).

draftjs appears in two shapes across entries -- newer content (current
year, most recently edited) uses the Wix Ricos "nodes" format, all prior
years use classic draft.js "blocks"+"entityMap". Both are parsed.

Link targets are either the Wix media CDN (usrfiles.com, direct PDF) or a
Google Drive "share" link (drive.google.com/file/d/<id>/view), which is
rewritten to the direct-download form (drive.google.com/uc?export=download).
Both work unauthenticated (public "anyone with the link" sharing).

Each monthly PDF carries a 3-column rolling table ("Items <M-2> <M-1>
<M>") -- only the *current* month's column (the release's own month, taken
from the link label, not by trying to infer table-header order) is kept,
so re-published overlap across consecutive releases doesn't double-count.

PDF text extractability is inconsistent release-to-release (digitally
authored vs. scanned/signed-then-scanned) -- roughly 1 in 7 releases in the
2021-2026 archive extract cleanly via pdfplumber; the rest are image-only
scans. No OCR fallback is wired here (would need pytesseract + pdf2image,
not currently a project dependency) -- image-only releases are skipped with
a logged warning rather than silently dropped. This recovers the extractable
subset now; OCR is the natural follow-up to backfill the rest.

Emits PriceObservation rows (analytical_role: official_avg).
coicop_classification: source_curated (small, stable ~20-item basket,
static _COICOP_MAP below, all COICOP division 01).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.eap.pacific_islands.american_samoa import _wix_faq
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_doc_bfi"
_IDENT = ["source_key", "observation_date", "item_name"]

_BFI_CATEGORY_TITLE = "Basic Food Index"
_BFI_CATEGORY_ID_FALLBACK = "0575ea83-521a-48a3-8afa-952065b7bd17"

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_MONTH_NUM = {m.lower(): i + 1 for i, m in enumerate(_MONTHS)}
_LABEL_DATE_RE = re.compile(
    r"(?P<month>" + "|".join(_MONTHS) + r")\s+(?P<year>\d{4})", re.IGNORECASE
)

# (keyword to match in the PDF's item label, canonical item_name, COICOP-2018
# code, unit). Matched case-insensitively as a substring, first hit wins --
# keep more specific keywords first.
_ITEM_RULES: list[tuple[str, str, str, str]] = [
    ("chicken", "10 Kg Case of Chicken", "01.1.2", "10kg"),
    ("pepsi", "Pepsi Can (12oz)", "01.2.2", "12oz"),
    ("fish", "Fresh Fish, per lb", "01.1.3", "lb"),
    ("water", "Bottled Water", "01.2.2", "each"),
    ("rice", "Rice (5lbs)", "01.1.1", "5lbs"),
    ("taro", "Taro, per lb (imported)", "01.1.7", "lb"),
    ("pork", "Pork Spare Ribs, per lb", "01.1.2", "lb"),
    ("milk", "Fresh Milk (carton)", "01.1.4", "carton"),
    ("chuck wagon", "Chuck Wagon (16oz) pkg", "01.1.2", "16oz"),
    ("banana", "Banana, per lb", "01.1.6", "lb"),
    ("ramen", "Ramen (85g) pkg", "01.1.1", "85g"),
    ("ice cream", "Ice Cream (2Liter)", "01.1.4", "2L"),
    ("tuna", "Iapana Tuna (6.5oz)", "01.1.3", "6.5oz"),
    ("bread", "Bread, Pritchard sliced, long", "01.1.1", "loaf"),
    ("turkey", "Turkey Tail, per lb", "01.1.2", "lb"),
    ("sugar", "Sugar Chelsea (2kg)", "01.1.8", "2kg"),
    ("egg", "Eggs, Nulaid (small) doz", "01.1.4", "doz"),
    ("mayo", "Mayonnaise (15oz) bottle", "01.1.9", "15oz"),
    ("corn beef", "Corn Beef Palm (11.5oz) can", "01.1.2", "11.5oz"),
    ("corned beef", "Corn Beef Palm (11.5oz) can", "01.1.2", "11.5oz"),
    ("butter", "Butter, 8oz (227g)", "01.1.5", "8oz"),
]

_ITEM_ROW_RE = re.compile(
    r"^(?P<label>[A-Za-z0-9][A-Za-z0-9,.'()/\-& ]*?)\s+"
    r"\$?\s*(?P<v1>[\d][\d,\s]*\.\d{2})\s+"
    r"\$?\s*(?P<v2>[\d][\d,\s]*\.\d{2})\s+"
    r"\$?\s*(?P<v3>[\d][\d,\s]*\.\d{2})\s*$"
)


def _match_item(label: str) -> tuple[str, str, str] | None:
    low = label.lower()
    for keyword, canonical, coicop, unit in _ITEM_RULES:
        if keyword in low:
            return canonical, coicop, unit
    return None


def _clean_price(raw: str) -> float | None:
    try:
        return float(raw.replace("$", "").replace(",", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _parse_pdf_current_month(
    pdf_bytes: bytes, obs_date: date, pdf_url: str
) -> list[dict]:
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if not text.strip():
        return []

    ts = get_scrape_ts()
    rows: list[dict] = []
    for line in text.splitlines():
        m = _ITEM_ROW_RE.match(line.strip())
        if not m:
            continue
        match = _match_item(m.group("label"))
        if not match:
            logger.warning(
                "[%s] no item mapping for %r — dropping row",
                _SOURCE_KEY,
                m.group("label"),
            )
            continue
        canonical_name, coicop, unit = match
        price = _clean_price(m.group("v3"))  # rightmost column = current month
        if price is None:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "item_name": canonical_name,
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": pdf_url,
            "notes": "American Samoa Basic Food Index monthly release",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_as_doc_bfi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )

    token = _wix_faq.get_faq_token(session, _SOURCE_KEY)
    if not token:
        return None
    category_id = _wix_faq.get_category_id(
        session, token, _BFI_CATEGORY_TITLE, _BFI_CATEGORY_ID_FALLBACK, _SOURCE_KEY
    )
    year_entries = _wix_faq.query_year_entries(session, token, category_id, _SOURCE_KEY)
    if not year_entries:
        logger.warning("[%s] no BFI year entries found", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    skipped_image_only = 0
    for entry in year_entries:
        links = _wix_faq.extract_links(entry.get("draftjs", ""))
        for label, url in links:
            m = _LABEL_DATE_RE.search(label)
            if not m:
                continue
            month_num = _MONTH_NUM.get(m.group("month").lower())
            year = int(m.group("year"))
            if month_num is None:
                continue
            obs_date = date(year, month_num, 1)
            if obs_date <= cutoff:
                continue
            pdf_url = _wix_faq.gdrive_direct(url)
            try:
                resp = session.get(pdf_url, timeout=60)
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] PDF fetch failed for %s: %s", _SOURCE_KEY, pdf_url, exc
                )
                continue
            month_rows = _parse_pdf_current_month(resp.content, obs_date, pdf_url)
            if not month_rows:
                skipped_image_only += 1
                logger.info(
                    "[%s] %s: no extractable text (image-only scan?) — skipped",
                    _SOURCE_KEY,
                    label,
                )
                continue
            rows.extend(month_rows)

    if skipped_image_only:
        logger.info(
            "[%s] %d release(s) skipped as image-only (no OCR fallback wired)",
            _SOURCE_KEY,
            skipped_image_only,
        )
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
