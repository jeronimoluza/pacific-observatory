"""Solomon Islands National Statistics Office (SINSO) — Consumer Price Index.

The SINSO CPI is published monthly as a PDF bulletin at statistics.gov.sb.
The live site is Imunify360-protected (415 on API calls), so post discovery
runs through the Wayback Machine WP JSON API which returns post metadata
without bot-challenge triggers. PDF downloads are attempted direct-first,
then via Wayback fallback.

Emits IndexObservation rows (analytical_role: cpi_benchmark).

CPI base period: 2017=100. Groups published in Table 1.0 of each bulletin.
SINSO group → COICOP-2018 mapping:

  Food & Non-Alcoholic Beverages           → 01
  Alcoholic beverages, tobacco & narcotics → 02
  Clothing & footwear                      → 03
  Housing, water, electricity, gas ...     → 04
  Furnishings, household equipment ...     → 05
  Health                                   → 06
  Transport                                → 07
  Communication                            → 08
  Recreation & culture                     → 09
  Education                                → 10
  Restaurants & hotels                     → 11
  Miscellaneous goods & services           → 12

Note: SINSO publishes 12 groups — COICOP division 13 is absent.
All-items headline row is dropped pending a sanctioned sentinel code.
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

_WB_API_URL = (
    "https://web.archive.org/web/2025/"
    "https://statistics.gov.sb/wp-json/wp/v2/posts"
    "?categories=14&per_page=24&_fields=link,title,date&orderby=date&order=desc"
)
_PDF_BASE = "https://statistics.gov.sb"
_WB_PDF_PREFIX = "https://web.archive.org/web/2026/"
_COUNTRY = "Solomon Islands"
_SOURCE_KEY = "sb_sinso_cpi"
_SOURCE_URL = "https://statistics.gov.sb/category/statistics/economic-statistics/consumer-price-index/"
_BASE_PERIOD = "2017=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_COICOP_COLUMNS = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
]

_TABLE1_HDR = re.compile(r"Table\s+1\.0", re.IGNORECASE)
_CHANGE_HDR = re.compile(r"Percentage Change", re.IGNORECASE)
_DATA_ROW_RE = re.compile(
    r"^(\d{4})?(January|February|March|April(?:/r)?|May|June|July|August|September|October|November|December)"
    r"\s+([\d.]+(?:\s+[\d.]+){11,})",
    re.MULTILINE | re.IGNORECASE,
)


_MONTH_NUM = {
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

_COICOP_LABELS = [
    "Food & Non-Alcoholic Beverages",
    "Alcoholic beverages, tobacco & narcotics",
    "Clothing & footwear",
    "Housing, water, electricity, gas & other fuels",
    "Furnishings, household equipment",
    "Health",
    "Transport",
    "Communication",
    "Recreation & culture",
    "Education",
    "Restaurants & hotels",
    "Miscellaneous goods & services",
]


def _parse_pdf_date(pdf_url: str) -> date | None:
    m = re.search(r"National-CPI-(\w+)-(\d{4})\.pdf", pdf_url, re.IGNORECASE)
    if m:
        month_name, year = m.group(1).lower(), int(m.group(2))
        month_num = _MONTH_NUM.get(month_name)
        if month_num:
            return date(year, month_num, 1)
    return None


def _extract_table10(text: str) -> list[tuple[date, str, float]]:
    all_matches = list(_TABLE1_HDR.finditer(text))
    if not all_matches:
        return []
    table_start = all_matches[-1]
    change_start = _CHANGE_HDR.search(text, table_start.end())
    table_text = text[
        table_start.start() : change_start.start() if change_start else len(text)
    ]

    current_year: int | None = None
    results: list[tuple[date, str, float]] = []

    for line in table_text.splitlines():
        stripped = line.strip()
        year_m = re.match(
            r"^(\d{4})(January|February|March|April|May|June|July|August|September|October|November|December)(.*)",
            stripped,
            re.IGNORECASE,
        )
        no_year_m = (
            re.match(
                r"^(January|February|March|April(?:/r)?|May|June|July|August|September|October|November|December)(.*)",
                stripped,
                re.IGNORECASE,
            )
            if not year_m
            else None
        )

        if year_m:
            current_year = int(year_m.group(1))
            month_name = year_m.group(2).lower()
            rest = year_m.group(3)
        elif no_year_m:
            month_name = no_year_m.group(1).lower().replace("/r", "")
            rest = no_year_m.group(2)
        else:
            continue

        month_num = _MONTH_NUM.get(month_name)
        if month_num is None or current_year is None:
            continue

        nums = re.findall(r"[\d]+\.[\d]+", rest)
        if len(nums) < 12:
            continue

        obs_date = date(current_year, month_num, 1)
        for i, coicop in enumerate(_COICOP_COLUMNS):
            try:
                results.append((obs_date, coicop, float(nums[i])))
            except (IndexError, ValueError):
                pass

    return results


def _fetch_pdf_text(session, pdf_url: str) -> str | None:
    for url in [pdf_url, _WB_PDF_PREFIX + pdf_url]:
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 200:
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:
            logger.debug(
                "[%s] PDF fetch attempt failed for %s: %s", _SOURCE_KEY, url, exc
            )
    return None


def fetch_sb_sinso_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_WB_API_URL, timeout=30)
    resp.raise_for_status()

    posts = resp.json()
    if not isinstance(posts, list):
        logger.warning("[%s] Unexpected API response shape", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    for post in posts:
        raw_date = post.get("date", "")
        try:
            pub_date = datetime.fromisoformat(raw_date).date()
        except (ValueError, TypeError):
            continue
        if pub_date <= cutoff:
            continue
        post_link = post.get("link", "")
        wb_post_link = post_link
        wb_resp = session.get(wb_post_link, timeout=30)
        if wb_resp.status_code != 200:
            logger.warning(
                "[%s] Could not fetch post page: %s", _SOURCE_KEY, wb_post_link
            )
            continue
        pdf_matches = re.findall(
            r'href="([^"]*statistics\.gov\.sb/wp-content/uploads/[^"]*\.pdf)"',
            wb_resp.text,
            re.IGNORECASE,
        )
        wb_pdf_matches = re.findall(
            r'href="([^"]*web\.archive\.org/web/[^"]*statistics\.gov\.sb/wp-content/uploads/[^"]*\.pdf)"',
            wb_resp.text,
            re.IGNORECASE,
        )
        pdf_url = None
        if pdf_matches:
            pdf_url = pdf_matches[0]
        elif wb_pdf_matches:
            pdf_url = wb_pdf_matches[0]
        else:
            logger.warning("[%s] No PDF link in post: %s", _SOURCE_KEY, wb_post_link)
            continue

        obs_date = _parse_pdf_date(pdf_url) or pub_date
        if obs_date <= cutoff:
            continue

        text = _fetch_pdf_text(session, pdf_url)
        if not text:
            logger.warning("[%s] Could not download PDF: %s", _SOURCE_KEY, pdf_url)
            continue

        group_rows = _extract_table10(text)
        if not group_rows:
            logger.warning(
                "[%s] No Table 1.0 data parsed from %s", _SOURCE_KEY, pdf_url
            )
            continue

        for row_date, coicop, idx_val in group_rows:
            if row_date <= cutoff:
                continue
            row = {
                "observation_date": row_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": idx_val,
                "index_base_period": _BASE_PERIOD,
                "source_url": pdf_url,
                "notes": _COICOP_LABELS[_COICOP_COLUMNS.index(coicop)]
                if coicop in _COICOP_COLUMNS
                else coicop,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
