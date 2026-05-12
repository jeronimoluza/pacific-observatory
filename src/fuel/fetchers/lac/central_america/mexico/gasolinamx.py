"""Mexico gasolinamx.com Wayback Machine fetcher.

gasolinamx.com publishes today's national-average price for Magna,
Premium and Diesel as a small widget on its homepage. The site only
exposes the live values, so historical series come from the Internet
Archive Wayback Machine.

Strategy: probe one snapshot per month-start from the cutoff onward.
The Wayback redirects ``/web/YYYYMMDD/url`` to the closest available
snapshot; we extract the real snapshot date from the redirected URL,
parse the prices, and dedupe by snapshot date.

Widget HTML (stable since 2019-Q1):

    <div class="row gprice ...">
      ...
      Magna <b>23.75</b> <span>Precio promedio nacional</span>
    </div>
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_LIVE_URL = "https://www.gasolinamx.com/"
_WAYBACK_FMT = "https://web.archive.org/web/{ts}/{url}"
_SNAPSHOT_RE = re.compile(r"/web/(\d{14})/")
_PRICE_RE = re.compile(r"(Magna|Premium|Diesel)\s+<b>([\d.]+)</b>")

_COUNTRY = "Mexico"
_CURRENCY = "MXN"
_SOURCE_KEY = "mx_gasolinamx_wayback"
_FIRST_VALID_SNAPSHOT = date(2019, 3, 1)
_REQUEST_DELAY_S = 1.5


def _month_iter(start: date, end: date):
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        yield date(y, m, 1)
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def _fetch_snapshot(session, requested_ts: str) -> tuple[date, dict[str, float]] | None:
    url = _WAYBACK_FMT.format(ts=requested_ts, url=_LIVE_URL)
    try:
        resp = session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
    except Exception:
        logger.warning("[mx_gasolinamx] Wayback request failed: %s", url)
        return None

    m = _SNAPSHOT_RE.search(resp.url)
    if not m:
        return None
    snap_ts = m.group(1)
    try:
        snap_date = datetime.strptime(snap_ts[:8], "%Y%m%d").date()
    except ValueError:
        return None

    prices: dict[str, float] = {}
    for product, price_str in _PRICE_RE.findall(resp.text):
        try:
            prices[product] = float(price_str)
        except ValueError:
            continue
    if not prices:
        return None
    return snap_date, prices


def fetch_mx_gasolinamx(cutoff: date) -> pd.DataFrame | None:
    """Fetch Mexico national-average retail prices from gasolinamx.com via Wayback."""
    today = datetime.now(timezone.utc).date()
    start = max(cutoff, _FIRST_VALID_SNAPSHOT)
    session = make_session()

    seen_snapshots: set[date] = set()
    rows: list[dict] = []

    for month in _month_iter(start, today):
        req_ts = month.strftime("%Y%m%d")
        result = _fetch_snapshot(session, req_ts)
        time.sleep(_REQUEST_DELAY_S)
        if result is None:
            continue
        snap_date, prices = result
        if snap_date <= cutoff:
            continue
        if snap_date in seen_snapshots:
            continue
        seen_snapshots.add(snap_date)
        for product, price in prices.items():
            rows.append(
                {
                    "observation_date": snap_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
        logger.info(
            "[mx_gasolinamx] %s → %s",
            snap_date,
            ", ".join(f"{k}={v}" for k, v in prices.items()),
        )

    if not rows:
        logger.info("[mx_gasolinamx] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[mx_gasolinamx] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
