"""Egypt Ministry of Petroleum fetcher: live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page and parse HTML price tables
"""

import logging
import time
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.petroleum.gov.eg/ar-eg/Pages/HomePage.aspx"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=www.petroleum.gov.eg/ar-eg/Pages/HomePage.aspx"
    "&output=json&fl=timestamp,statuscode"
)
_WAYBACK_TPL = (
    "https://web.archive.org/web/{ts}"
    "/https://www.petroleum.gov.eg/ar-eg/Pages/HomePage.aspx"
)

_COUNTRY = "Egypt, Arab Rep."
_CURRENCY = "EGP"
_SOURCE_KEY = "eg_petroleum_gov"
_WAYBACK_SLEEP = 2

_PRODUCT_MAP: dict[str, tuple[str, str]] = {
    "كيروسين": ("Kerosene", "L"),
    "سولار": ("Diesel", "L"),
    "بوتاجاز": ("LPG", "cylinder"),
    "بنزين 80": ("Gasoline 80", "L"),
    "بنزين 92": ("Gasoline 92", "L"),
    "بنزين 95": ("Gasoline 95", "L"),
}


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_prices(html: str) -> list[dict]:
    """Extract retail fuel prices from the two homepage price tables."""
    soup = BeautifulSoup(html, "lxml")
    wrapper = soup.find("div", class_="PetrolPrice")
    if not wrapper:
        return []

    rows: list[dict] = []
    for panel in wrapper.find_all("div", class_=["PetrolProducts", "Petrollocal"]):
        table = panel.find_next("table")
        if not table:
            continue

        for table_row in table.find_all("tr"):
            cells = table_row.find_all("td")
            if len(cells) < 3:
                continue

            name_ar = cells[1].get_text(strip=True)
            if name_ar not in _PRODUCT_MAP:
                continue

            price = _parse_price(cells[2].get_text(strip=True))
            if price is None:
                continue

            name_en, unit = _PRODUCT_MAP[name_ar]
            rows.append(
                {
                    "fuel_product": name_en,
                    "price_local": price,
                    "unit": unit,
                }
            )

    return rows


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
    return _make_rows(raw, snapshot_date.strftime("%Y-%m-%d"))


def _fetch_live(session) -> list[dict]:
    resp = session.get(_LIVE_URL, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    return _make_rows(raw, today.strftime("%Y-%m-%d"))


def fetch_eg_petroleum(cutoff: date) -> pd.DataFrame | None:
    """Fetch Egypt fuel prices from petroleum.gov.eg."""
    session = make_session()
    all_rows: list[dict] = []

    timestamps = _discover_snapshots(session, cutoff)
    for index, timestamp in enumerate(timestamps):
        if index > 0:
            time.sleep(_WAYBACK_SLEEP)
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
        logger.warning(
            "Live petroleum.gov.eg page unreachable; using Wayback-only results"
        )

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
