"""OOMCO (Oman Oil Marketing Company) fetcher — live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page → parse HTML fuel price cards

Prices are set monthly by the Omani government. Displayed in Baiza/Liter,
converted to OMR/Liter for storage (1 OMR = 1000 Baiza).
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


# ── HTML parser ─────────────────────────────────────────────────────────────


def _parse_prices(html: str) -> list[dict]:
    """Extract fuel prices from the OOMCO homepage fuel-prices section."""
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", class_="fuel-prices")
    if not container:
        return []

    rows: list[dict] = []
    for col in container.find_all("div", class_="col-sm-3"):
        name_el = col.find("div", class_="h5")
        price_el = col.find("div", class_="h2")
        if not name_el or not price_el:
            continue

        name = name_el.get_text(strip=True)
        price_text = price_el.get_text(strip=True)

        match = _PRICE_RE.search(price_text)
        if not match:
            continue

        price_bzs = int(match.group(1))
        price_omr = round(price_bzs / 1000, 3)

        rows.append(
            {
                "fuel_product": name,
                "price_local": price_omr,
                "unit": "L",
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
    for row in data[1:]:
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
    """Fetch the current OOMCO page and parse it."""
    resp = session.get(_LIVE_URL, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    obs_str = _round_to_first(today)
    return _make_rows(raw, obs_str)


# ── Main fetcher ────────────────────────────────────────────────────────────


def fetch_oomco(cutoff: date) -> pd.DataFrame | None:
    """Fetch Oman fuel prices from OOMCO (live + Wayback backfill)."""
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
        logger.warning("Live OOMCO page unreachable — using Wayback-only results")

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
