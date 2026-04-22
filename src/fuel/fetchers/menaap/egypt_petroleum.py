"""Egypt Ministry of Petroleum fetcher — live site + Wayback Machine backfill.

Scraping strategy (2-phase):
  Phase 1: Query Wayback CDX API for ALL archived snapshots after cutoff
  Phase 2: Fetch each snapshot + live page → parse HTML price tables

Source: https://www.petroleum.gov.eg/ar-eg/Pages/HomePage.aspx
  - Two price boxes: "منتجات" (Products) + "بنزين محلي" (Domestic Gasoline)
  - Prices are government-administered, changed by decree (irregular intervals)
  - All snapshots stored raw — dedup happens in a later process stage
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

# Arabic product name → (English name, unit)
_PRODUCT_MAP: dict[str, tuple[str, str]] = {
    "كيروسين": ("Kerosene", "L"),
    "سولار": ("Diesel", "L"),
    "بوتاجاز": ("LPG", "cylinder"),
    "بنزين 80": ("Gasoline 80", "L"),
    "بنزين 92": ("Gasoline 92", "L"),
    "بنزين 95": ("Gasoline 95", "L"),
}

_WAYBACK_SLEEP = 2  # seconds between Wayback requests


def _parse_price(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


# ── HTML parser ─────────────────────────────────────────────────────────────


def _parse_prices(html: str) -> list[dict]:
    """Extract retail fuel prices from the two price tables on the homepage."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    wrapper = soup.find("div", class_="PetrolPrice")
    if not wrapper:
        return rows

    for panel in wrapper.find_all("div", class_=["PetrolProducts", "Petrollocal"]):
        table = panel.find_next("table")
        if not table:
            continue

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue

            name_ar = tds[1].get_text(strip=True)
            if name_ar not in _PRODUCT_MAP:
                continue

            price = _parse_price(tds[2].get_text(strip=True))
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
    """Query CDX API for ALL snapshot timestamps after cutoff (status 200 only)."""
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
    """Fetch one Wayback snapshot, parse it, return rows with snapshot date."""
    url = _WAYBACK_TPL.format(ts=ts)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    snap_date = date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
    obs_str = snap_date.strftime("%Y-%m-%d")
    return _make_rows(raw, obs_str)


# ── Live fetch ──────────────────────────────────────────────────────────────


def _fetch_live(session) -> list[dict]:
    """Fetch the current petroleum.gov.eg page and parse it."""
    resp = session.get(_LIVE_URL, timeout=30)
    resp.raise_for_status()

    raw = _parse_prices(resp.text)
    today = datetime.now(timezone.utc).date()
    obs_str = today.strftime("%Y-%m-%d")
    return _make_rows(raw, obs_str)


# ── Main fetcher ────────────────────────────────────────────────────────────


def fetch_eg_petroleum(cutoff: date) -> pd.DataFrame | None:
    """Fetch Egypt fuel prices from petroleum.gov.eg (live + Wayback backfill)."""
    session = make_session()
    all_rows: list[dict] = []

    # Phase 1: Wayback backfill — ALL snapshots, no dedup
    timestamps = _discover_snapshots(session, cutoff)
    for i, ts in enumerate(timestamps):
        if i > 0:
            time.sleep(_WAYBACK_SLEEP)
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
        logger.warning(
            "Live petroleum.gov.eg page unreachable — using Wayback-only results"
        )

    if not all_rows:
        return None

    return pd.DataFrame(all_rows)
