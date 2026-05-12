"""Wayback Machine helpers shared by SAR fetchers.

The CDX endpoint lives at https://web.archive.org/cdx/search/cdx and may be
rate-limited or briefly unreachable. Callers should treat any failure as
fall-through (return live-only data) rather than aborting.

Wayback intermittently rejects bursts (TCP RST / connection refused) under
load — both CDX queries and snapshot fetches are retried with exponential
backoff so a single transient blip does not lose the whole backfill.
"""

import json
import logging
import time
from datetime import date

import requests

from core.http import make_session

logger = logging.getLogger(__name__)

CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_RAW = "https://web.archive.org/web/{ts}id_/{url}"

# Retries here are about transport errors (refused/timeout), not 4xx/5xx.
_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY = 2.0  # seconds; doubles each attempt


def _request_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    timeout: int = 60,
    label: str = "wayback",
) -> requests.Response | None:
    last_exc: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            resp = session.get(
                url, params=params, timeout=timeout, allow_redirects=True
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt + 1 < _RETRY_ATTEMPTS:
                delay = _RETRY_BASE_DELAY * (2**attempt)
                logger.debug(
                    "[%s] transient error (attempt %d/%d): %s — retrying in %.1fs",
                    label,
                    attempt + 1,
                    _RETRY_ATTEMPTS,
                    exc,
                    delay,
                )
                time.sleep(delay)
    logger.warning(
        "[%s] giving up after %d attempts: %s", label, _RETRY_ATTEMPTS, last_exc
    )
    return None


def discover_snapshots(
    session: requests.Session,
    url: str,
    cutoff: date,
    *,
    collapse_digits: int = 6,
    timeout: int = 60,
) -> list[str]:
    """Query Wayback CDX and return sorted timestamps after cutoff.

    `collapse_digits` deduplicates within a calendar window:
      6 = same year-month, 8 = same calendar day, 4 = same year.
    Returns an empty list (logged) if Wayback is unreachable.
    """
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp,statuscode,mimetype",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": f"timestamp:{collapse_digits}",
        "from": cutoff.strftime("%Y%m%d"),
    }
    resp = _request_with_retry(
        session, CDX_URL, params=params, timeout=timeout, label="wayback CDX"
    )
    if resp is None:
        return []
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[wayback] CDX returned non-JSON for %s: %s", url, exc)
        return []

    if not data or len(data) < 2:
        return []

    timestamps: list[str] = []
    for row in data[1:]:
        if not row or not row[0]:
            continue
        timestamps.append(row[0])
    timestamps.sort()
    logger.info("[wayback] %d snapshots for %s after %s", len(timestamps), url, cutoff)
    return timestamps


def fetch_snapshot(
    session: requests.Session,
    timestamp: str,
    url: str,
    *,
    timeout: int = 60,
) -> str | None:
    """Fetch a single Wayback snapshot's raw HTML (no toolbar injection)."""
    snap_url = WAYBACK_RAW.format(ts=timestamp, url=url)
    resp = _request_with_retry(
        session, snap_url, timeout=timeout, label=f"wayback snap {timestamp}"
    )
    return resp.text if resp is not None else None


def iterate_snapshots(
    url: str,
    cutoff: date,
    *,
    collapse_digits: int = 6,
    throttle_seconds: float = 1.0,
):
    """Yield (snapshot_date, html) pairs for snapshots after cutoff."""
    session = make_session()
    timestamps = discover_snapshots(
        session, url, cutoff, collapse_digits=collapse_digits
    )
    if not timestamps:
        return

    for i, ts in enumerate(timestamps):
        if i > 0:
            time.sleep(throttle_seconds)
        snap_date = _parse_timestamp(ts)
        if snap_date is None:
            continue
        html = fetch_snapshot(session, ts, url)
        if html is None:
            continue
        yield snap_date, html


def _parse_timestamp(ts: str) -> date | None:
    """Wayback timestamps are 14-digit YYYYMMDDHHMMSS — extract the date."""
    if len(ts) < 8:
        return None
    try:
        return date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
    except ValueError:
        return None
