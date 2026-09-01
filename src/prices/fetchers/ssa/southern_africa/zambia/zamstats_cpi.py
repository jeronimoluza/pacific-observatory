"""ZamStats "The Monthly" bulletin — Consumer Price Index by division, Zambia.

The Zambia Statistics Agency (zamstats.gov.zm) monthly bulletin carries
"Table 1.2: Consumer Price Index by Division" — a 2009=100 index series
covering "All Items" plus 12 COICOP-1999-style divisions (Food and
Non-Alcoholic Beverages ... Miscellaneous Goods and Services), published
monthly back to January 2023 within the same PDF. Re-verified live
2026-09-01 against Volume 281 (August 2026): last row "August 558.72 ..."
(13 values), plausible index trajectory (All Items rising from 377.25 in
Jan 2023 to 558.72 in Aug 2026, consistent with the bulletin's own stated
6.2% annual inflation figure).

Shares bulletin discovery with the sibling `zamstats_avg_prices` fetcher
(same PDF, different table) — see that module's docstring for the WP REST
API discovery method and why the post slug is not predictable in advance.
Kept as a separate fetcher per the "don't mix PriceObservation and
IndexObservation in one fetcher" rule (Table 7 is PriceObservation, Table
1.2 here is IndexObservation).

PDF PARSING: each data row is one physical line, "<Month> <13 floats>"
(all 13 columns render on one line, unlike Table 7's wrapped item
descriptions) — the year is a separately-positioned label pdfplumber
places mid-block (a rotated axis label in the source PDF, not aligned to
any single row), so this fetcher does NOT attempt to recover a year per
row from that label. Instead, only the LAST row in the table is taken
(the most recent point), and its calendar month/year is assigned from the
bulletin's own release period (parsed from the WP post slug, e.g.
'monthly-inflation-august-2026' -> 2026-08) — the same value Table 7's
sibling fetcher uses, and the two are cross-checked implicitly since the
bulletin's title month must match the last CPI row's month name for this
to be correct (confirmed live 2026-09-01: bulletin='August 2026', last
Table 1.2 row month='August').

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled (ZamStats' own division labels
mapped to COICOP 01-12; a 12-division pre-2018-revision scheme, same
vintage as Jordan DOS CPI / Tunisia INS IPC in this corpus). "All Items"
is dropped — no sanctioned all-items COICOP sentinel (see skill's open
design question).
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Zambia"
_SOURCE_KEY = "zamstats_cpi"
_BASE_PERIOD = "2009=100"
_POSTS_API = "https://www.zamstats.gov.zm/wp-json/wp/v2/posts"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_PDF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
_TABLE_HEADING = "Table 1.2: Consumer Price Index by Division"
_ROW_RE = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<nums>(?:-?[\d,]+\.\d{2}\s+){12}-?[\d,]+\.\d{2})$"
)

# Column order as it appears in the source table, index 0 = "All Items"
# (dropped — no sanctioned sentinel).
_DIVISION_ORDER = [
    None,  # All Items
    "01",  # Food and Non-Alcoholic Beverages
    "02",  # Alcoholic Beverages and Tobacco
    "03",  # Clothing and Footwear
    "04",  # Housing, Water, Electricity, Gas and Other Fuels
    "05",  # Furnishing, Household Equipment and Routine Hse Mtc
    "06",  # Health
    "07",  # Transport
    "08",  # Communication
    "09",  # Recreation and Culture
    "10",  # Education
    "11",  # Restaurants and Hotels
    "12",  # Miscellaneous Goods and Services
]


def _find_latest_bulletin_pdf(session) -> tuple[str, str] | None:
    try:
        resp = session.get(
            _POSTS_API,
            params={
                "search": "Monthly",
                "orderby": "date",
                "order": "desc",
                "per_page": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] wp-json posts lookup failed: %s", _SOURCE_KEY, exc)
        return None

    for post in posts:
        slug = post.get("slug", "")
        if not slug.startswith("monthly-inflation-"):
            continue
        content = post.get("content", {}).get("rendered", "")
        m = _PDF_RE.search(content)
        if m:
            return m.group(1), slug
    return None


def _slug_to_period(slug: str) -> str | None:
    months = {
        m: i + 1
        for i, m in enumerate(
            [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ]
        )
    }
    parts = slug.replace("monthly-inflation-", "").split("-")
    found = None
    for i in range(len(parts) - 1):
        mon = parts[i].lower()
        if mon in months and parts[i + 1].isdigit() and len(parts[i + 1]) == 4:
            found = (int(parts[i + 1]), months[mon])
    if not found:
        return None
    year, month = found
    return date(year, month, 1).isoformat()


def _extract_latest_division_row(pdf_bytes: bytes) -> list[float] | None:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        target_text = None
        for p in pdf.pages:
            t = p.extract_text() or ""
            if _TABLE_HEADING in t:
                target_text = t
                break
    if not target_text:
        return None

    rows = []
    for line in target_text.split("\n"):
        m = _ROW_RE.match(line.strip())
        if m:
            nums = [float(x.replace(",", "")) for x in m.group("nums").split()]
            if len(nums) == 13:
                rows.append(nums)
    return rows[-1] if rows else None


def fetch_zamstats_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_bulletin_pdf(session)
    if not found:
        logger.warning("[%s] could not resolve latest bulletin post", _SOURCE_KEY)
        return None
    pdf_url, slug = found

    obs_date = _slug_to_period(slug)
    if not obs_date:
        logger.warning("[%s] could not parse period from slug %r", _SOURCE_KEY, slug)
        return None
    if date.fromisoformat(obs_date) <= cutoff:
        logger.info(
            "[%s] latest bulletin (%s) is at/before cutoff=%s",
            _SOURCE_KEY,
            obs_date,
            cutoff,
        )
        return None

    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] pdf fetch failed: %s", _SOURCE_KEY, exc)
        return None

    values = _extract_latest_division_row(resp.content)
    if not values:
        logger.warning(
            "[%s] no CPI-by-division row parsed from %s", _SOURCE_KEY, pdf_url
        )
        return None

    ts = get_scrape_ts()
    rows = []
    for coicop, val in zip(_DIVISION_ORDER, values):
        if coicop is None:
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": round(val, 4),
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "notes": "ZamStats 'The Monthly' bulletin, Table 1.2 (latest month row)",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info(
        "[%s] %d rows for %s (cutoff=%s)", _SOURCE_KEY, len(rows), obs_date, cutoff
    )
    return pd.DataFrame(rows) if rows else None
