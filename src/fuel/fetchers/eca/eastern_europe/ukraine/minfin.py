"""Minfin Ukraine regional fuel prices fetcher.

Scraping strategy (2-phase):
  Phase 1: Discover oblast list from /markets/fuel/reg/ (~23 oblasts).
  Phase 2: For each oblast × month whose range intersects the cutoff,
           fetch /markets/fuel/reg/{slug}/YYYY-MM/ and parse the daily
           price table (date × 5 fuels: А 95+, А 95, А 92, ДТ, Газ).

Oblast names and prices are preserved as published by Minfin — no renaming,
no currency/unit conversion, no derived national averages. Regional archive
starts around 2020-01.
"""

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://index.minfin.com.ua"
_INDEX_URL = f"{_BASE_URL}/markets/fuel/reg/"

_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "minfin_ua_regional_daily"

_FETCH_SLEEP = 0.5  # polite throttle between requests

_OBLAST_HREF_RE = re.compile(r"^/markets/fuel/reg/([a-z_-]+)/$")
_DATE_CELL_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})")

_FUEL_COLUMNS = ("А 95+", "А 95", "А 92", "ДТ", "Газ")


def _normalize(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _parse_price(text: str) -> float | None:
    cleaned = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        val = float(cleaned)
    except (ValueError, TypeError):
        return None
    return val if val > 0 else None


def _discover_oblasts(session) -> list[tuple[str, str]]:
    """Return (slug, display_name) tuples for each oblast Minfin publishes."""
    resp = session.get(_INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        match = _OBLAST_HREF_RE.match(a["href"])
        if not match:
            continue
        slug = match.group(1)
        if slug in seen:
            continue
        name = _normalize(a.get_text())
        if not name:
            continue
        seen.add(slug)
        found.append((slug, name))
    return found


def _months_to_fetch(cutoff: date) -> list[tuple[int, int]]:
    """(year, month) pairs from cutoff's month through the current month."""
    now = datetime.now(timezone.utc).date()
    months: list[tuple[int, int]] = []
    year, month = cutoff.year, cutoff.month
    while (year, month) <= (now.year, now.month):
        months.append((year, month))
        month += 1
        if month > 12:
            year += 1
            month = 1
    return months


def _parse_month_page(
    html: str,
    cutoff: date,
    oblast_name: str,
) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []

    header_row = table.find("tr")
    if header_row is None:
        return []
    headers = [_normalize(c.get_text()) for c in header_row.find_all(["th", "td"])]

    col_idx: dict[str, int] = {}
    for idx, label in enumerate(headers):
        if label in _FUEL_COLUMNS:
            col_idx[label] = idx
    if not col_idx:
        return []

    rows_out: list[dict] = []
    for tr in table.find_all("tr")[1:]:
        cells = [_normalize(c.get_text()) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        date_match = _DATE_CELL_RE.match(cells[0])
        if not date_match:
            continue
        try:
            obs = date(
                int(date_match.group(3)),
                int(date_match.group(2)),
                int(date_match.group(1)),
            )
        except ValueError:
            continue
        if obs <= cutoff:
            continue

        iso = obs.strftime("%Y-%m-%d")
        for fuel, idx in col_idx.items():
            if idx >= len(cells):
                continue
            price = _parse_price(cells[idx])
            if price is None:
                continue
            rows_out.append(
                {
                    "observation_date": iso,
                    "country": _COUNTRY,
                    "subnational_area": oblast_name,
                    "fuel_product": fuel,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "liter",
                    "source_key": _SOURCE_KEY,
                }
            )
    return rows_out


def fetch_minfin_ua(cutoff: date) -> pd.DataFrame | None:
    """Fetch Ukraine regional (oblast-level) fuel prices from index.minfin.com.ua."""
    session = make_session()

    oblasts = _discover_oblasts(session)
    if not oblasts:
        logger.warning("[minfin_ua] No oblasts discovered")
        return None
    logger.info("[minfin_ua] %d oblasts discovered", len(oblasts))

    months = _months_to_fetch(cutoff)
    if not months:
        logger.info("[minfin_ua] No months after cutoff %s", cutoff)
        return None

    all_rows: list[dict] = []
    total_requests = len(oblasts) * len(months)
    logger.info(
        "[minfin_ua] Fetching %d oblast-months (cutoff=%s)",
        total_requests,
        cutoff,
    )

    for slug, name in oblasts:
        for year, month in months:
            url = f"{_BASE_URL}/markets/fuel/reg/{slug}/{year:04d}-{month:02d}/"
            try:
                resp = session.get(url, timeout=30)
            except Exception:
                logger.exception("[minfin_ua] Request failed: %s", url)
                time.sleep(_FETCH_SLEEP)
                continue
            if resp.status_code == 404:
                time.sleep(_FETCH_SLEEP)
                continue
            try:
                resp.raise_for_status()
            except Exception:
                logger.warning(
                    "[minfin_ua] %s → HTTP %s", url, resp.status_code
                )
                time.sleep(_FETCH_SLEEP)
                continue

            rows = _parse_month_page(resp.text, cutoff, name)
            if rows:
                all_rows.extend(rows)
                logger.info(
                    "[minfin_ua] %s %04d-%02d: %d rows",
                    slug,
                    year,
                    month,
                    len(rows),
                )
            time.sleep(_FETCH_SLEEP)

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows)
    df = df.sort_values(
        ["observation_date", "subnational_area", "fuel_product"]
    ).reset_index(drop=True)
    logger.info("[minfin_ua] Returning %d rows", len(df))
    return df
