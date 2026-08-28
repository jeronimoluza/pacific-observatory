"""Wayback Machine transport helpers for the prices pipeline.

Adapted from src/fuel/fetchers/_shared/sar/wayback.py. Differences:
- Defaults to daily collapse (`timestamp:8`) rather than monthly.
- Uses the `id_/` snapshot endpoint so the returned HTML has no IA toolbar
  injection, preserving the CSS structure the spiders' selectors expect.
- Adds jitter to the exponential backoff (IA tends to refuse synchronized
  retries from concurrent workers).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from collections.abc import Iterator
from datetime import date
from urllib.parse import urlsplit

import requests

from prices._shared.pacing import CircuitBreaker, RateLimiter

logger = logging.getLogger(__name__)

CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_RAW = "https://web.archive.org/web/{ts}id_/{url}"

_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY = 2.0  # seconds; doubles each attempt
_THROTTLE_STATUS = (429, 503)


def _retry_after_seconds(exc: requests.RequestException) -> float | None:
    """Return the Retry-After delay (seconds form) for a 429/503, else None."""
    resp = getattr(exc, "response", None)
    if resp is None or resp.status_code not in _THROTTLE_STATUS:
        return None
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None  # HTTP-date form is unsupported; fall back to backoff


def _is_throttle_failure(exc: requests.RequestException) -> bool:
    """True for connection-refused (TCP blackhole) and 429/503 responses."""
    if isinstance(exc, requests.ConnectionError):
        return True
    resp = getattr(exc, "response", None)
    return resp is not None and resp.status_code in _THROTTLE_STATUS


def _request_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict | None = None,
    timeout: int = 60,
    label: str = "wayback",
    limiter: RateLimiter | None = None,
    breaker: CircuitBreaker | None = None,
) -> requests.Response | None:
    last_exc: Exception | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        if breaker is not None:
            breaker.wait_if_open()
        if limiter is not None:
            limiter.wait()
        try:
            resp = session.get(
                url, params=params, timeout=timeout, allow_redirects=True
            )
            resp.raise_for_status()
            if breaker is not None:
                breaker.record_success()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            retry_after = _retry_after_seconds(exc)
            if breaker is not None and _is_throttle_failure(exc):
                cooldown = breaker.record_failure()
                if cooldown is not None:
                    logger.warning(
                        "[%s] circuit breaker tripped — pausing %.0fs", label, cooldown
                    )
            if attempt + 1 < _RETRY_ATTEMPTS:
                base = _RETRY_BASE_DELAY * (2**attempt)
                delay = base + random.uniform(0, base / 2)
                if retry_after is not None:
                    delay = max(delay, retry_after)
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
    logger.info("[wayback] %d snapshots for %s after %s", len(timestamps), url, cutoff)
    return timestamps


def collapse_timestamps(timestamps: list[str], granularity: str) -> list[str]:
    """Client-side dedup of 14-digit timestamps to one per calendar bucket.

    granularity ∈ {"day","week","month","year"}. Keeps the earliest snapshot
    in each bucket. `week` uses the ISO calendar (year-week), which has no
    digit-prefix equivalent — the reason weekly collapse can't be pushed to
    the CDX server and must happen here.
    """
    buckets: dict[str, str] = {}
    for ts in sorted(timestamps):
        if len(ts) < 8:
            continue
        if granularity == "year":
            key = ts[:4]
        elif granularity == "month":
            key = ts[:6]
        elif granularity == "week":
            d = parse_timestamp_to_date(ts)
            if d is None:
                continue
            iy, iw, _ = d.isocalendar()
            key = f"{iy}{iw:02d}"
        else:  # day (default)
            key = ts[:8]
        buckets.setdefault(key, ts)  # sorted asc → first seen is earliest
    return sorted(buckets.values())


def _norm_url(u: str) -> str | None:
    """Scheme-insensitive key for intersecting CDX `original` with our URLs."""
    try:
        s = urlsplit(u if "//" in u else f"//{u}")
    except ValueError:
        return None
    host = s.netloc.lower()
    if not host:
        return None
    path = s.path.rstrip("/")
    query = f"?{s.query}" if s.query else ""
    return f"{host}{path}{query}"


def _strip_query(norm: str) -> str:
    """Drop the query string from a `_norm_url` key.

    Storefronts hand out per-variant URLs (`/products/foo?variant=123`) while
    Wayback archives the canonical `/products/foo`. Matching on the full key
    alone silently discards those captures, so `bulk_discover` falls back to
    this looser key when the exact one misses.
    """
    return norm.split("?", 1)[0]


def _derive_scopes(urls: list[str]) -> list[tuple[str, str]]:
    """Group URLs by host → (scope, matchType='prefix') per host.

    The scope is the host plus the longest common path prefix (trimmed to the
    last '/'), so a single-tenant retailer collapses to a tight product prefix
    while a multi-tenant host (item.rakuten.co.jp) falls back to host-level.
    """
    by_host: dict[str, list[str]] = {}
    for u in urls:
        try:
            s = urlsplit(u if "//" in u else f"//{u}")
        except ValueError:
            continue
        if s.netloc:
            by_host.setdefault(s.netloc.lower(), []).append(s.path)
    scopes: list[tuple[str, str]] = []
    for host, paths in by_host.items():
        lcp = os.path.commonprefix(paths)
        cut = lcp.rfind("/")
        prefix_path = lcp[: cut + 1] if cut >= 0 else ""
        scopes.append((f"{host}{prefix_path}", "prefix"))
    return scopes


# Safety cap on CDX pages per scope — a runaway backstop, not a real limit.
_MAX_BULK_PAGES = 500


def iter_bulk_captures(
    session: requests.Session,
    scope: str,
    match_type: str,
    cutoff: date,
    *,
    timeout: int = 60,
) -> Iterator[tuple[str, str]]:
    """Yield (original_url, timestamp) for every 200/text-html capture in scope.

    One prefix/host CDX query paged via the CDX-server `page=` API — the bulk
    analogue of per-URL discovery. Pages until an empty page rather than
    trusting `showNumPages` (which is flaky under load and returns non-integer
    output when `output=json` is set); a single unpaged call is unsafe because
    CDX caps rows and, sorted by urlkey, the cap can fill entirely with sibling
    paths (e.g. `/product-category/`) before reaching the product pages.

    No server-side collapse: collapsing adjacent rows on a multi-URL query
    would drop the first capture of a URL whenever it shares a bucket with the
    previous URL's last capture. Dedup is the caller's via `collapse_timestamps`.
    """
    base = {
        "url": scope,
        "matchType": match_type,
        "output": "json",
        "fl": "original,timestamp",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "from": cutoff.strftime("%Y%m%d"),
    }
    for pg in range(_MAX_BULK_PAGES):
        resp = _request_with_retry(
            session,
            CDX_URL,
            params=dict(base, page=pg),
            timeout=timeout,
            label=f"wayback CDX p{pg}",
        )
        if resp is None:
            # Transient failure after retries — stop rather than risk skipping
            # a page silently; the caller keeps whatever was yielded so far.
            logger.warning("[wayback] bulk paging stopped early at page %d", pg)
            break
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            break
        rows = data[1:] if len(data) >= 2 else []
        if not rows:
            break  # empty page → past the end
        for row in rows:
            if len(row) >= 2 and row[0] and row[1]:
                yield row[0], row[1]
    else:
        logger.warning(
            "[wayback] hit _MAX_BULK_PAGES=%d for scope=%s — captures may be truncated",
            _MAX_BULK_PAGES,
            scope,
        )


def bulk_discover(
    session: requests.Session,
    universe: list[dict],
    cutoff: date,
    *,
    granularity: str = "week",
    timeout: int = 60,
    include_unmatched: bool = False,
    scope_prefix: str | None = None,
    path_re: str | None = None,
) -> tuple[dict[str, list[str]], list[dict]]:
    """Return ({url_hash: collapsed_timestamps}, newly_discovered_entries).

    Replaces one CDX call per URL with one paged CDX query per host.

    Matching is two-pass: exact normalized URL first, then the same key with
    its query string dropped (see `_strip_query`).

    `include_unmatched=False` (the default, "scraped" universe) intersects
    captures with `universe`, so only products we collected live get
    backfilled. `include_unmatched=True` (the "archive" universe) also keeps
    captures for URLs absent from `universe` — products delisted before we
    ever scraped the site — synthesizing `url_hash = md5(url)` to match the
    convention in `backfill.load_url_universe`. Those entries are returned as
    the second element, shaped like `universe` rows, for the caller to append.

    `scope_prefix` overrides the CDX scope derived from `universe` — required
    in archive mode, where the scraped set is exactly what must not bound the
    query. `path_re` filters newly discovered URLs by path (matched URLs are
    never filtered; we already know they are product pages).
    """
    normmap: dict[str, str] = {}
    normmap_noq: dict[str, str] = {}
    for e in universe:
        n = _norm_url(e["url"])
        if n:
            normmap[n] = e["url_hash"]
            normmap_noq.setdefault(_strip_query(n), e["url_hash"])

    pattern = re.compile(path_re) if path_re else None
    if include_unmatched and pattern is None:
        logger.warning(
            "[wayback] archive universe with no path_re — category and static "
            "pages under the scope will be fetched and parsed as products"
        )

    buckets: dict[str, list[str]] = {}
    discovered: dict[str, dict] = {}
    if scope_prefix:
        scopes = [(scope_prefix, "prefix")]
    else:
        scopes = _derive_scopes([e["url"] for e in universe])
    for scope, match_type in scopes:
        logger.info("[wayback] bulk CDX scope=%s match=%s", scope, match_type)
        for original, ts in iter_bulk_captures(
            session, scope, match_type, cutoff, timeout=timeout
        ):
            n = _norm_url(original)
            if not n:
                continue
            h = normmap.get(n) or normmap_noq.get(_strip_query(n))
            if h is None:
                if not include_unmatched:
                    continue
                if pattern is not None and not pattern.search(urlsplit(original).path):
                    continue
                h = hashlib.md5(original.encode()).hexdigest()
                discovered.setdefault(
                    h,
                    {"url": original, "url_hash": h, "earliest_scraped_at": None},
                )
            buckets.setdefault(h, []).append(ts)

    return (
        {h: collapse_timestamps(v, granularity) for h, v in buckets.items()},
        sorted(discovered.values(), key=lambda r: r["url_hash"]),
    )


def fetch_snapshot(
    session: requests.Session,
    timestamp: str,
    url: str,
    *,
    timeout: int = 60,
    limiter: RateLimiter | None = None,
    breaker: CircuitBreaker | None = None,
) -> str | None:
    """Fetch a single Wayback snapshot's raw HTML (no toolbar injection).

    The `id_` suffix on the wayback path returns the original archived bytes
    without IA's playback wrapper, which is essential for keeping the price
    spiders' selectors intact.
    """
    snap_url = WAYBACK_RAW.format(ts=timestamp, url=url)
    resp = _request_with_retry(
        session,
        snap_url,
        timeout=timeout,
        label=f"wayback snap {timestamp}",
        limiter=limiter,
        breaker=breaker,
    )
    return resp.text if resp is not None else None


def parse_timestamp_to_date(ts: str) -> date | None:
    """Wayback timestamps are 14-digit YYYYMMDDHHMMSS — extract the date."""
    if len(ts) < 8:
        return None
    try:
        return date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))
    except ValueError:
        return None
