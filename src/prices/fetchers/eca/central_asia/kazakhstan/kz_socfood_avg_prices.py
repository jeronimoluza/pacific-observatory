"""Kazakhstan Bureau of National Statistics — average prices for socially
important food products, national + per-city, published weekly.

stat.gov.kz/en/industries/economy/prices/ lists recent publications; the
target document's title is "Price index and average prices for socially
important food products in the Republic of Kazakhstan (as DD Month YYYY)"
and links to /api/iblock/element/<id>/file/en/, which 302-redirects to a
signed /upload/iblock/... XLSX URL. The workbook has one sheet per table
("Content" sheet lists them); the target table is sheet "5. Average prices
for socially important food products as of <date>" -- located by scanning
sheet A1 text rather than trusting the literal sheet name "5", since that
could shift if a table is added/removed in a future edition. Column B
("By surveyed cities") is the national average; columns C onward are the
~21 individual surveyed cities (not extracted here -- national only, like
the Rosstat fetcher's territory-643 row).

Item labels occasionally carry an explicit unit after the last comma
("Milk (...), liter", "Eggs, category 1, dozen", "Sunflower oil, liter");
everything else in this list (grains, meats, fish, cheese, produce, sugar,
salt, tea) is priced per kg, the implicit default for this particular
survey.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://stat.gov.kz/en/industries/economy/prices/"
_COUNTRY = "Kazakhstan"
_CURRENCY = "KZT"
_SOURCE_KEY = "kz_socfood_avg_prices"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_NATIONAL_COL = "By surveyed cities"
_UNIT_WORDS = {"liter", "dozen", "kg"}

_DOC_RE = re.compile(
    r'href="(/api/iblock/element/\d+/file/en/)"[^>]*>\s*'
    r'<span class="doc-item-title">\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
_TARGET_TITLE_RE = re.compile(
    r"average prices for socially important food products", re.IGNORECASE
)
_SHEET_TITLE_RE = re.compile(
    r"average prices for socially important food products", re.IGNORECASE
)
_DATE_RE = re.compile(r"as of ([A-Za-z]+ \d{1,2},\s*\d{4})")


def _find_doc_url(html: str) -> str | None:
    for href, title in _DOC_RE.findall(html):
        if _TARGET_TITLE_RE.search(title):
            return "https://stat.gov.kz" + href
    return None


def _parse_obs_date(cell0: str) -> date | None:
    m = _DATE_RE.search(cell0)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def _split_unit(label: str) -> tuple[str, str]:
    if "," in label:
        head, tail = label.rsplit(",", 1)
        if tail.strip().lower() in _UNIT_WORDS:
            return head.strip(), tail.strip().lower()
    return label.strip(), "kg"


def _parse_avg_sheet(df: pd.DataFrame, obs_date: date, doc_url: str) -> list[dict]:
    header_row = df.iloc[2]
    try:
        national_col = header_row.tolist().index(_NATIONAL_COL)
    except ValueError:
        logger.warning("[%s] no '%s' column in sheet", _SOURCE_KEY, _NATIONAL_COL)
        return []

    ts = get_scrape_ts()
    rows: list[dict] = []
    for i in range(3, len(df)):
        label = df.iloc[i, 0]
        if not isinstance(label, str) or not label.strip():
            continue
        value = df.iloc[i, national_col]
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        item_name, unit = _split_unit(label)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "weekly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": doc_url,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_kz_socfood_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_INDEX_URL, timeout=30)
        page.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    doc_url = _find_doc_url(page.text)
    if not doc_url:
        logger.warning(
            "[%s] no matching document link found on index page", _SOURCE_KEY
        )
        return None

    try:
        resp = session.get(doc_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] document fetch failed: %s", _SOURCE_KEY, exc)
        return None

    try:
        xl = pd.ExcelFile(io.BytesIO(resp.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx parse failed: %s", _SOURCE_KEY, exc)
        return None

    target_df = None
    obs_date = None
    for sheet_name in xl.sheet_names:
        df = xl.parse(sheet_name, header=None)
        if df.empty:
            continue
        cell0 = str(df.iloc[0, 0])
        if _SHEET_TITLE_RE.search(cell0):
            target_df = df
            obs_date = _parse_obs_date(cell0)
            break

    if target_df is None or obs_date is None:
        logger.warning("[%s] target sheet or date not found in workbook", _SOURCE_KEY)
        return None

    if obs_date <= cutoff:
        return None

    rows = _parse_avg_sheet(target_df, obs_date, doc_url)
    logger.info(
        "[%s] %d rows for %s (cutoff=%s)", _SOURCE_KEY, len(rows), obs_date, cutoff
    )
    return pd.DataFrame(rows) if rows else None
