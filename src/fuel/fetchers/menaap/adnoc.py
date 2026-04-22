"""ADNOC Distribution UAE fetcher — live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page → parse HTML price cards

Prices are set monthly by the UAE Fuel Price Committee on the 1st.
All observation dates are rounded to the 1st of their month.
"""

import logging
import time
from datetime import date, timezone, datetime

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

# Tab ID → (product name suffix, unit)
# Products within each tab are identified by their fuel-text <p> content.
_TAB_UNITS: dict[str, str] = {
    "Fuel": "L",
    "LPG-25": "cylinder",
    "LPG-50": "cylinder",
    "LPG-Composite": "cylinder",
    "EV": "kW",
}

# Suffix appended to product name for LPG tabs to disambiguate identical
# "Refill Cylinder" / "New Cylinder" names across tabs.
_TAB_SUFFIX: dict[str, str] = {
    "LPG-25": " (LPG 25 lb)",
    "LPG-50": " (LPG 50 lb)",
    "LPG-Composite": " (LPG Composite)",
}


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


# ── HTML parser ─────────────────────────────────────────────────────────────


def _parse_prices(html: str) -> list[dict]:
    """Extract prices from all tab panes in the ADNOC consumer-fuel page."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    for tab_id, unit in _TAB_UNITS.items():
        pane = soup.find("div", id=tab_id)
        if not pane:
            continue

        suffix = _TAB_SUFFIX.get(tab_id, "")
        for li in pane.find_all("li", class_="featured-tabs-card__price-item"):
            price_el = li.find("h4", class_="featured-tabs-card__price")
            name_el = li.find("p", class_="featured-tabs-card__fuel-text")
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


def _round_to_first(d: date) -> str:
    return date(d.year, d.month, 1).strftime("%Y-%m-%d")


def _make_rows(raw: list[dict], obs_date_str: str) -> list[dict]:
    return [
        {
            "observation_date": obs_date_str,
            "country": _COUNTRY,
            "fuel_product": r["fuel_product"],
            "price_local": r["price_local"],
            "currency": _CURRENCY,
            "unit": r["unit"],
            "source_key": _SOURCE_KEY,
        }
        for r in raw
    ]


# ── Wayback Machine integration ────────────────────────────────────────────


def _discover_snapshots(session, cutoff: date) -> list[str]:
    """Query CDX API for snapshot timestamps after cutoff (status 200 only)."""
    try:
        resp = session.get(_CDX_URL, timeout=30)
        resp.raise_for_status()
    except Exception:
        logger.warning("CDX API unavailable — falling back to live-only")
        return []

    data = resp.json()
    if not data or len(data) < 2:
        return []

    timestamps: list[str] = []
    for row in data[1:]:  # skip header row
        ts, status = row[0], row[1]
        if status != "200":
            continue
        snap_date = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
        if snap_date > cutoff:
            timestamps.append(ts)

    timestamps.sort()
    logger.info("CDX: %d snapshots after cutoff %s", len(timestamps), cutoff)
    return timestamps


def _fetch_wayback_snapshot(session, ts: str) -> list[dict]:
    """Fetch one Wayback snapshot, parse it, return rows with rounded date."""
    url = _WAYBACK_TPL.format(ts=ts)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    snap_date = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
    obs_str = _round_to_first(snap_date)
    return _make_rows(raw, obs_str)


# ── Live fetch ──────────────────────────────────────────────────────────────


def _fetch_live(session) -> list[dict]:
    """Fetch the current ADNOC page and parse it."""
    resp = session.get(_LIVE_URL, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    obs_str = _round_to_first(today)
    return _make_rows(raw, obs_str)


# ── Main fetcher ────────────────────────────────────────────────────────────


def fetch_adnoc(cutoff: date) -> pd.DataFrame | None:
    """Fetch UAE fuel prices from ADNOC Distribution (live + Wayback backfill)."""
    session = make_session()
    all_rows: list[dict] = []

    # Phase 1: Wayback backfill
    timestamps = _discover_snapshots(session, cutoff)
    for i, ts in enumerate(timestamps):
        if i > 0:
            time.sleep(1)
        try:
            rows = _fetch_wayback_snapshot(session, ts)
            all_rows.extend(rows)
            logger.info("Wayback %s: %d products", ts[:8], len(rows))
        except Exception:
            logger.exception("Failed to fetch Wayback snapshot %s", ts[:8])
            continue

    # Phase 2: Live fetch
    try:
        rows = _fetch_live(session)
        all_rows.extend(rows)
        logger.info("Live: %d products", len(rows))
    except Exception:
        logger.warning("Live ADNOC page unreachable — using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
