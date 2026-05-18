"""South Africa retail petrol prices from FIASA (fuelsindustry.org.za).

Parses two layers of the public 'fuel-prices-current-past' page:

* Historical years (2012–prev) live in static ``tablepress-YYYY`` HTML.
* The current calendar year lives in two wpDataTables (``#table_1`` for
  Coastal, ``#table_2`` for Gauteng) populated by JS, so we render the
  page with Playwright before parsing.

The fetcher keeps only the retail 95 ULP rows (marked '*') and emits a
monthly national-average price in ZAR/L (mean of Coastal and Gauteng).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from html import unescape

import pandas as pd

logger = logging.getLogger(__name__)

_URL = "https://fuelsindustry.org.za/consumer-information/fuel-prices-current-past/"
_COUNTRY = "South Africa"
_CURRENCY = "ZAR"
_SOURCE_KEY = "fuelsindustry_za_retail_petrol"

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_HISTORICAL_TABLE_RE = re.compile(
    r'<table id="tablepress-(?P<year>20\d{2})"[^>]*>(?P<body>[\s\S]*?)</table>'
)
_CURRENT_TABLE_RE = re.compile(r'<table id="(table_[12])"[\s\S]*?</table>')
_ROW_RE = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>")
_CELL_RE = re.compile(r"<t[hd][^>]*>([\s\S]*?)</t[hd]>")
_TAG_RE = re.compile(r"<[^>]+>")
_RETAIL_95_ULP_RE = re.compile(r"^\s*95\s*ULP\s*\(c/l\)\s*\*?\s*$", re.IGNORECASE)
_CURRENT_HEADER_RE = re.compile(r"(\d{1,2})-([A-Za-z]{3})-(\d{2})")


def _strip(cell: str) -> str:
    return unescape(_TAG_RE.sub("", cell)).replace("\xa0", " ").strip()


def _parse_cents(raw: str) -> float | None:
    s = raw.strip()
    if not s or s == "-":
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        value = float(s)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_month_header(header: str) -> int | None:
    for token in header.replace("\xa0", " ").split():
        m = _MONTHS.get(token[:3].lower())
        if m:
            return m
    return None


def _render_page(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context().new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            try:
                page.wait_for_function(
                    "document.querySelectorAll('#table_2 tbody tr td').length > 0",
                    timeout=20000,
                )
            except Exception:
                logger.warning(
                    "[fuelsindustry_za] current-year wpDataTable did not render — "
                    "historical data only"
                )
            return page.content()
        finally:
            browser.close()


def _parse_year_table(
    year: int, body: str
) -> dict[int, tuple[float | None, float | None]]:
    """Return {month: (coastal, gauteng)} for a static tablepress-YYYY body."""
    rows = _ROW_RE.findall(body)
    if not rows:
        return {}
    header_cells = [_strip(c) for c in _CELL_RE.findall(rows[0])]
    if len(header_cells) < 13:
        return {}
    months = [_parse_month_header(h) for h in header_cells[1:13]]
    section: str | None = None
    coastal: dict[int, float] = {}
    gauteng: dict[int, float] = {}
    for raw in rows[1:]:
        cells = [_strip(c) for c in _CELL_RE.findall(raw)]
        if not cells:
            continue
        upper = cells[0].upper()
        if upper == "COASTAL":
            section = "coastal"
            continue
        if upper == "GAUTENG":
            section = "gauteng"
            continue
        if upper.startswith("NOTES"):
            section = None
            continue
        if section not in {"coastal", "gauteng"}:
            continue
        if not _RETAIL_95_ULP_RE.match(cells[0]):
            continue
        values = cells[1:13]
        if len(values) != 12:
            continue
        target = coastal if section == "coastal" else gauteng
        for month, raw_v in zip(months, values):
            if month is None:
                continue
            price = _parse_cents(raw_v)
            if price is not None:
                target[month] = price
    out: dict[int, tuple[float | None, float | None]] = {}
    for month in range(1, 13):
        out[month] = (coastal.get(month), gauteng.get(month))
    return out


def _parse_current_tables(html: str) -> dict[date, tuple[float | None, float | None]]:
    """Return {first-of-month-date: (coastal, gauteng)} from #table_1 / #table_2."""
    coastal: dict[date, float] = {}
    gauteng: dict[date, float] = {}
    for m in _CURRENT_TABLE_RE.finditer(html):
        tid = m.group(1)
        is_coastal = tid == "table_1"
        body = m.group(0)
        rows = _ROW_RE.findall(body)
        if not rows:
            continue
        header_cells = [_strip(c) for c in _CELL_RE.findall(rows[0])]
        if len(header_cells) < 2:
            continue
        years: list[int] = []
        parsed_headers: list[tuple[int, int] | None] = []
        for h in header_cells[1:]:
            mh = _CURRENT_HEADER_RE.search(h.replace(" ", ""))
            if mh:
                month = _MONTHS.get(mh.group(2).lower()[:3])
                year = 2000 + int(mh.group(3))
                if month:
                    parsed_headers.append((year, month))
                    years.append(year)
                    continue
            parsed_headers.append(None)
        if not years:
            continue
        year_mode = max(set(years), key=years.count)
        col_dates: list[date | None] = []
        for ph in parsed_headers:
            if ph is None:
                col_dates.append(None)
            else:
                _, month = ph
                col_dates.append(date(year_mode, month, 1))
        for raw in rows[1:]:
            cells = [_strip(c) for c in _CELL_RE.findall(raw)]
            if not cells or not _RETAIL_95_ULP_RE.match(cells[0]):
                continue
            target = coastal if is_coastal else gauteng
            for dt, val in zip(col_dates, cells[1:]):
                if dt is None:
                    continue
                price = _parse_cents(val)
                if price is not None:
                    target[dt] = price
            break
    keys = sorted(set(coastal) | set(gauteng))
    return {k: (coastal.get(k), gauteng.get(k)) for k in keys}


def _to_rows(
    year: int,
    monthly: dict[int, tuple[float | None, float | None]],
) -> list[dict]:
    rows: list[dict] = []
    for month, (c, g) in monthly.items():
        if c is None or g is None:
            continue
        avg_cents = (c + g) / 2.0
        rows.append(
            {
                "observation_date": date(year, month, 1).isoformat(),
                "country": _COUNTRY,
                "fuel_product": "Petrol 95",
                "price_local": round(avg_cents / 100.0, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "litre",
            }
        )
    return rows


def fetch_fuelsindustry_za(cutoff: date) -> pd.DataFrame | None:
    html = _render_page(_URL)
    rows: list[dict] = []
    for m in _HISTORICAL_TABLE_RE.finditer(html):
        year = int(m.group("year"))
        rows.extend(_to_rows(year, _parse_year_table(year, m.group("body"))))
    current = _parse_current_tables(html)
    for dt, (c, g) in current.items():
        if c is None or g is None:
            continue
        avg_cents = (c + g) / 2.0
        rows.append(
            {
                "observation_date": dt.isoformat(),
                "country": _COUNTRY,
                "fuel_product": "Petrol 95",
                "price_local": round(avg_cents / 100.0, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "litre",
            }
        )
    cutoff_iso = cutoff.isoformat()
    rows = [r for r in rows if r["observation_date"] > cutoff_iso]
    if not rows:
        logger.info("[fuelsindustry_za] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values("observation_date")
        .reset_index(drop=True)
    )
    logger.info(
        "[fuelsindustry_za] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_fuelsindustry_za"]
