"""OOMCO Oman fetcher: live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page and parse HTML fuel price cards

Prices are displayed in Baiza/Liter and converted to OMR/Liter for storage.
All observation dates are rounded to the 1st of their month.
"""

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.oomco.com/"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=www.oomco.com/"
    "&output=json&fl=timestamp,statuscode"
)
_WAYBACK_TPL = "https://web.archive.org/web/{ts}/https://www.oomco.com/"

_COUNTRY = "Oman"
_CURRENCY = "OMR"
_SOURCE_KEY = "oomco_monthly"

_PRICE_RE = re.compile(r"(\d+)\s*Bzs/Liter", re.IGNORECASE)


def _parse_prices(html: str) -> list[dict]:
    """Extract fuel prices from the OOMCO homepage fuel-prices section."""
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", class_="fuel-prices")
    if not container:
        return []

    rows: list[dict] = []
    for column in container.find_all("div", class_="col-sm-3"):
        name_el = column.find("div", class_="h5")
        price_el = column.find("div", class_="h2")
        if not name_el or not price_el:
            continue

        match = _PRICE_RE.search(price_el.get_text(strip=True))
        if not match:
            continue

        rows.append(
            {
                "fuel_product": name_el.get_text(strip=True),
                "price_local": round(int(match.group(1)) / 1000, 3),
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


def _discover_snapshots(session, cutoff: date) -> list[str]:
    """Query CDX API for snapshot timestamps after cutoff."""
    try:
        resp = session.get(_CDX_URL, timeout=30)
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
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    snapshot_date = date(int(timestamp[:4]), int(timestamp[4:6]), int(timestamp[6:8]))
    return _make_rows(raw, _round_to_first(snapshot_date))


def _fetch_live(session) -> list[dict]:
    resp = session.get(_LIVE_URL, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    return _make_rows(raw, _round_to_first(today))


def fetch_oomco(cutoff: date) -> pd.DataFrame | None:
    """Fetch Oman fuel prices from OOMCO."""
    session = make_session()
    all_rows: list[dict] = []

    timestamps = _discover_snapshots(session, cutoff)
    for index, timestamp in enumerate(timestamps):
        if index > 0:
            time.sleep(1)
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
        logger.warning("Live OOMCO page unreachable; using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
