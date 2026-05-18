"""Gibraltar — GibOil ``Live Price Checker`` widget (live + Wayback backfill).

The widget at https://giboil.com/ renders four prices in GBP per litre:

    Regular Unleaded (UNL 95)  £1.079
    Premium Unleaded (UNL 98)  £1.200
    Diesel                     £1.255
    Ad Blue (via Dispenser…)   £0.80

There is no on-page date — each observation is dated by the fetch time (live)
or the Wayback snapshot date (backfill). The widget first appeared in Wayback
snapshots in June 2024; earlier snapshots have no prices.
"""

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd

from core.http import make_session
from fuel.fetchers._shared.sar.wayback import iterate_snapshots

logger = logging.getLogger(__name__)

_URL = "https://giboil.com/"
_COUNTRY = "Gibraltar"
_CURRENCY = "GBP"
_SOURCE_KEY = "gi_giboil_daily"

# Each pattern captures the price for a single labelled product.
_PRODUCT_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "Regular Unleaded (UNL 95)",
        re.compile(r"Regular\s+Unleaded[^£]{0,80}£\s*([0-9]+\.[0-9]+)", re.I),
    ),
    (
        "Premium Unleaded (UNL 98)",
        re.compile(r"Premium\s+Unleaded[^£]{0,80}£\s*([0-9]+\.[0-9]+)", re.I),
    ),
    (
        "Diesel",
        re.compile(r"\bDiesel\b[^£]{0,80}£\s*([0-9]+\.[0-9]+)", re.I),
    ),
    (
        "Ad Blue",
        re.compile(r"Ad\s*Blue[^£]{0,140}£\s*([0-9]+\.[0-9]+)", re.I),
    ),
]


def _parse(html: str, obs_date: date) -> list[dict]:
    # The "Live Price Checker" anchor is the only place all four product
    # lines appear together; if it's missing we're on an older layout.
    if "Live Price" not in html and "Unleaded" not in html:
        return []
    # Collapse to plain text for stable regex matching.
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    obs_str = obs_date.isoformat()
    rows: list[dict] = []
    for product, pattern in _PRODUCT_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            price = float(m.group(1))
        except ValueError:
            continue
        if not (price > 0):
            continue
        rows.append(
            {
                "observation_date": obs_str,
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": price,
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "L",
            }
        )
    return rows


def _fetch_live() -> list[dict]:
    session = make_session()
    try:
        resp = session.get(_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[gi_giboil] live fetch failed")
        return []
    return _parse(resp.text, datetime.now(timezone.utc).date())


def fetch_gi_giboil(cutoff: date) -> pd.DataFrame | None:
    """Fetch Gibraltar fuel prices from giboil.com — Wayback backfill + live."""
    seen: set[tuple[str, str]] = set()
    all_rows: list[dict] = []

    for snap_date, html in iterate_snapshots(_URL, cutoff, collapse_digits=6):
        if snap_date <= cutoff:
            continue
        for row in _parse(html, snap_date):
            key = (row["observation_date"], row["fuel_product"])
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    for row in _fetch_live():
        if datetime.strptime(row["observation_date"], "%Y-%m-%d").date() <= cutoff:
            continue
        key = (row["observation_date"], row["fuel_product"])
        if key in seen:
            continue
        seen.add(key)
        all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
