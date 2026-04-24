"""Saudi Aramco fetcher: live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page and parse Sitecore JSON for prices

Aramco publishes retail fuel prices at /en/what-we-do/energy-products/retail-fuels.
The page is a React SSR app (Sitecore) that embeds prices in the server-rendered
JSON as factDescription/factNumber pairs. Wayback captures this JSON.

Gasoline prices update monthly (announced on 10th, effective 11th).
Diesel prices update yearly in January.
"""

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
import requests


logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.aramco.com/en/what-we-do/energy-products/retail-fuels"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=www.aramco.com/en/what-we-do/energy-products/retail-fuels"
    "&output=json&fl=timestamp,statuscode"
)
_WAYBACK_TPL = (
    "https://web.archive.org/web/{ts}"
    "/https://www.aramco.com/en/what-we-do/energy-products/retail-fuels"
)

_COUNTRY = "Saudi Arabia"
_CURRENCY = "SAR"
_SOURCE_KEY = "aramco_monthly"

# Regex to find factDescription/factNumber pairs in Sitecore JSON
_FACT_RE = re.compile(
    r'"factDescription":\{"value":"([^"]+)"\},' r'"factNumber":\{"value":"([^"]+)"\}'
)

# Product names we care about (case-insensitive matching)
_PRODUCT_MAP = {
    "gasoline 91": "Gasoline 91",
    "gasoline 95": "Gasoline 95",
    "gasoline 98": "Gasoline 98",
    "diesel": "Diesel",
    "kerosene": "Kerosene",
    "lpg": "LPG",
}


def _parse_prices(html: str) -> list[dict]:
    """Extract fuel prices from Aramco Sitecore JSON embedded in HTML."""
    rows: list[dict] = []
    seen: set[str] = set()

    for match in _FACT_RE.finditer(html):
        description = match.group(1).strip()
        value_str = match.group(2).strip()

        key = description.lower()
        product_name = None
        for pattern, canonical in _PRODUCT_MAP.items():
            if pattern in key:
                product_name = canonical
                break

        if not product_name or product_name in seen:
            continue

        try:
            price = float(value_str)
        except (ValueError, TypeError):
            continue

        if price <= 0:
            continue

        seen.add(product_name)
        rows.append(
            {
                "fuel_product": product_name,
                "price_local": price,
                "unit": "L",
            }
        )

    return rows


def _round_to_first(observation_date: date) -> str:
    return date(observation_date.year, observation_date.month, 1).strftime("%Y-%m-%d")


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

    raw = _parse_prices(resp.text)
    snapshot_date = date(int(timestamp[:4]), int(timestamp[4:6]), int(timestamp[6:8]))
    return _make_rows(raw, _round_to_first(snapshot_date))


def _fetch_live(session) -> list[dict]:
    resp = session.get(_LIVE_URL, timeout=60)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    return _make_rows(raw, _round_to_first(today))


def fetch_aramco(cutoff: date) -> pd.DataFrame | None:
    """Fetch Saudi Arabia fuel prices from Aramco."""
    # Plain session — make_session() browser headers cause Akamai timeouts
    session = requests.Session()
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
        logger.warning("Live Aramco page unreachable; using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
