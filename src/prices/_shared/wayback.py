"""Wayback Machine transport helpers for the prices pipeline.

Adapted from src/fuel/fetchers/_shared/sar/wayback.py. Differences:
- Defaults to daily collapse (`timestamp:8`) rather than monthly.
- Uses the `id_/` snapshot endpoint so the returned HTML has no IA toolbar
  injection, preserving the CSS structure the spiders' selectors expect.
- Adds jitter to the exponential backoff (IA tends to refuse synchronized
  retries from concurrent workers).
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import date

import requests

logger = logging.getLogger(__name__)

CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_RAW = "https://web.archive.org/web/{ts}id_/{url}"

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
                base = _RETRY_BASE_DELAY * (2**attempt)
                delay = base + random.uniform(0, base / 2)
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
    collapse_digits: int = 8,
    timeout: int = 60,
) -> list[str]:
    """Query CDX and return sorted 14-digit timestamps with statuscode 200.

    `collapse_digits` deduplicates within a calendar window:
      8 = same day (default), 6 = same month, 4 = same year.
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
    logger.info(
        "[wayback] %d snapshots for %s after %s", len(timestamps), url, cutoff
    )
    return timestamps
