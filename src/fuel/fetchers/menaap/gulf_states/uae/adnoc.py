"""ADNOC Distribution UAE fetcher: live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page and parse HTML price cards

Prices are set monthly by the UAE Fuel Price Committee on the 1st.
All observation dates are rounded to the 1st of their month.
"""

import logging
import time
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.adnocdistribution.ae/en/consumer-fuel"
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=www.adnocdistribution.ae/en/consumer-fuel"
    "&output=json&fl=timestamp,statuscode"
)
_WAYBACK_TPL = (
    "https://web.archive.org/web/{ts}/https://www.adnocdistribution.ae/en/consumer-fuel"
)

_COUNTRY = "United Arab Emirates"
_CURRENCY = "AED"
_SOURCE_KEY = "adnoc_monthly"

_TAB_UNITS: dict[str, str] = {
    "Fuel": "L",
    "LPG-25": "cylinder",
    "LPG-50": "cylinder",
    "LPG-Composite": "cylinder",
    "EV": "kW",
}
_TAB_SUFFIX: dict[str, str] = {
    "LPG-25": " (LPG 25 lb)",
    "LPG-50": " (LPG 50 lb)",
    "LPG-Composite": " (LPG Composite)",
}


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_prices(html: str) -> list[dict]:
    """Extract prices from all tab panes in the ADNOC consumer-fuel page."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    for tab_id, unit in _TAB_UNITS.items():
        pane = soup.find("div", id=tab_id)
        if not pane:
            continue

        suffix = _TAB_SUFFIX.get(tab_id, "")
        for item in pane.find_all("li", class_="featured-tabs-card__price-item"):
            price_el = item.find("h4", class_="featured-tabs-card__price")
            name_el = item.find("p", class_="featured-tabs-card__fuel-text")
            if not price_el or not name_el:
                continue

            price = _parse_price(price_el.get_text())
            name = name_el.get_text(strip=True)
            if price is None or not name:
                continue

            rows.append(
                {
                    "fuel_product": name + suffix,
                    "price_local": price,
                    "unit": unit,
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


def fetch_adnoc(cutoff: date) -> pd.DataFrame | None:
    """Fetch UAE fuel prices from ADNOC Distribution."""
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
        logger.warning("Live ADNOC page unreachable; using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
