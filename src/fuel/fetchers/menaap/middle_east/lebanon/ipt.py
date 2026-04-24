"""IPT Lebanon fetcher: live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page and parse HTML price table

IPT publishes weekly fuel prices at /ipt/en/our-stations/fuel-prices.
Prices are in Lebanese Lira (L.L.) per 20 liters (pre-2021) or per liter.
The page has an ASP.NET date picker but Wayback captures the server-rendered
prices in static HTML tables.

Products: UNL 95, UNL 98, Diesel, Gas (LPG).
Product names vary across years (UNL 95, Gasoline 95, Gasoline UNL 95).
"""

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.iptgroup.com.lb/ipt/en/our-stations/fuel-prices"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=www.iptgroup.com.lb/ipt/en/our-stations/fuel-prices"
    "&output=json&fl=timestamp,statuscode"
)
_WAYBACK_TPL = (
    "https://web.archive.org/web/{ts}"
    "/https://www.iptgroup.com.lb/ipt/en/our-stations/fuel-prices"
)

_COUNTRY = "Lebanon"
_CURRENCY = "LBP"
_SOURCE_KEY = "ipt_weekly"

# Map raw product names to canonical names (case-insensitive matching)
_PRODUCT_PATTERNS = {
    "95": "UNL 95",
    "98": "UNL 98",
    "diesel": "Diesel",
    "gas": "Gas (LPG)",
    "lpg": "Gas (LPG)",
}

# Date pattern in IPT headings: DD / MM / YYYY
_DATE_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})")


def _classify_product(raw_name: str) -> str | None:
    """Map a raw product name to a canonical name."""
    lower = raw_name.lower()
    for pattern, canonical in _PRODUCT_PATTERNS.items():
        if pattern in lower:
            return canonical
    return None


def _parse_prices(html: str) -> tuple[list[dict], date | None]:
    """Extract fuel prices and observation date from IPT HTML."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    seen: set[str] = set()

    # Extract prices from <strong class="priceSpanWidth"> elements
    for strong in soup.find_all("strong", class_=re.compile(r"priceSpanWidth")):
        price_text = strong.get_text(strip=True)

        # Parse price: "1,403,000 L.L." or "26,400 L.L." or just "26,400"
        price_clean = price_text.replace("L.L.", "").replace(",", "").strip()
        try:
            price = float(price_clean)
        except (ValueError, TypeError):
            continue

        if price <= 0:
            continue

        # Get product name from the previous <td> sibling
        td = strong.find_parent("td")
        if not td:
            continue
        prev_td = td.find_previous_sibling("td")
        if not prev_td:
            continue

        raw_name = prev_td.get_text(strip=True)
        canonical = _classify_product(raw_name)
        if not canonical or canonical in seen:
            continue

        seen.add(canonical)
        rows.append(
            {
                "fuel_product": canonical,
                "price_local": price,
                "unit": "L",
            }
        )

    # Extract observation date from page
    obs_date = None
    date_match = _DATE_RE.search(html)
    if date_match:
        day, month, year = (
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
        )
        try:
            obs_date = date(year, month, day)
        except ValueError:
            pass

    return rows, obs_date


def _make_rows(raw: list[dict], obs_date_str: str) -> list[dict]:
    return [
        {
            "observation_date": obs_date_str,
            "country": _COUNTRY,
            "fuel_product": row["fuel_product"],
            "price_local": row["price_local"],
            "currency": _CURRENCY,
            "unit": row["unit"],
            "source_key": _SOURCE_KEY,
        }
        for row in raw
    ]


def _round_to_first(observation_date: date) -> str:
    return date(observation_date.year, observation_date.month, 1).strftime("%Y-%m-%d")


def _discover_snapshots(cutoff: date) -> list[str]:
    """Query CDX API for snapshot timestamps after cutoff."""
    try:
        # Use a plain session for CDX — make_session() browser headers cause timeouts
        cdx_session = requests.Session()
        resp = cdx_session.get(_CDX_URL, timeout=30)
        resp.raise_for_status()
    except Exception:
        logger.warning("CDX API unavailable; falling back to live-only")
        return []

    data = resp.json()
    if not data or len(data) < 2:
        return []

    timestamps: list[str] = []
    for row in data[1:]:
        timestamp, status = row[0], row[1]
        if status != "200":
            continue
        snapshot_date = date(
            int(timestamp[:4]), int(timestamp[4:6]), int(timestamp[6:8])
        )
        if snapshot_date > cutoff:
            timestamps.append(timestamp)

    timestamps.sort()
    logger.info("CDX: %d snapshots after cutoff %s", len(timestamps), cutoff)
    return timestamps


def _fetch_wayback_snapshot(session, timestamp: str) -> list[dict]:
    url = _WAYBACK_TPL.format(ts=timestamp)
    resp = session.get(url, timeout=60)
    resp.raise_for_status()

    raw, page_date = _parse_prices(resp.text)
    # Prefer the date from the page content; fall back to snapshot timestamp
    if page_date:
        obs_date_str = _round_to_first(page_date)
    else:
        snapshot_date = date(
            int(timestamp[:4]), int(timestamp[4:6]), int(timestamp[6:8])
        )
        obs_date_str = _round_to_first(snapshot_date)

    return _make_rows(raw, obs_date_str)


def _fetch_live(session) -> list[dict]:
    resp = session.get(_LIVE_URL, timeout=60)
    resp.raise_for_status()

    raw, page_date = _parse_prices(resp.text)
    if page_date:
        obs_date_str = _round_to_first(page_date)
    else:
        today = datetime.now(timezone.utc).date()
        obs_date_str = _round_to_first(today)

    return _make_rows(raw, obs_date_str)


def fetch_ipt(cutoff: date) -> pd.DataFrame | None:
    """Fetch Lebanon fuel prices from IPT."""
    session = make_session()
    all_rows: list[dict] = []

    timestamps = _discover_snapshots(cutoff)
    for index, timestamp in enumerate(timestamps):
        if index > 0:
            time.sleep(3)
        try:
            rows = _fetch_wayback_snapshot(session, timestamp)
            all_rows.extend(rows)
            logger.info("Wayback %s: %d products", timestamp[:8], len(rows))
        except Exception:
            logger.exception("Failed to fetch Wayback snapshot %s", timestamp[:8])

    try:
        rows = _fetch_live(session)
        all_rows.extend(rows)
        logger.info("Live: %d products", len(rows))
    except Exception:
        logger.warning("Live IPT page unreachable; using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
