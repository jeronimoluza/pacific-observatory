"""Common Crawl index resolution + per-spider archive scope.

Both pieces used to be hand-maintained here. Now:

- The per-spider scope is read from the YAML manifests' ``archive_prefix`` /
  ``archive_path_re`` fields — the same pair the Wayback backfill uses — so a
  spider gets a Common Crawl path the moment it is onboarded, instead of only
  when someone remembers to edit this file.
- The index set is resolved live from ``collinfo.json`` rather than pinned to a
  handful of recent crawls, because the point of Common Crawl here is
  historical depth. :data:`_FALLBACK_CC_INDEXES` covers the offline case.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"

# Earliest crawl year worth querying. Common Crawl reaches back to 2008, but
# the e-commerce product pages this pipeline parses are thin before ~2013 and
# every extra index is another index query per spider.
DEFAULT_CC_SINCE_YEAR = 2013

# Used only when collinfo.json is unreachable. Verified live 2026-08-04.
_FALLBACK_CC_INDEXES: List[str] = [
    "CC-MAIN-2026-30",
    "CC-MAIN-2026-25",
    "CC-MAIN-2026-21",
    "CC-MAIN-2026-17",
    "CC-MAIN-2026-12",
    "CC-MAIN-2026-08",
    "CC-MAIN-2026-04",
    "CC-MAIN-2025-51",
]

_INDEX_ID_RE = re.compile(r"^CC-MAIN-(\d{4})-\d+$")


@lru_cache(maxsize=4)
def resolve_cc_indexes(since_year: int = DEFAULT_CC_SINCE_YEAR) -> List[str]:
    """Return every ``CC-MAIN-<year>-<week>`` index from `since_year` on.

    Newest first, matching the order ``collinfo.json`` publishes. Falls back to
    :data:`_FALLBACK_CC_INDEXES` when the fetch fails, so an offline run still
    does something useful rather than crashing.
    """
    try:
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "20", "--max-time", "60", COLLINFO_URL],
            capture_output=True,
            text=True,
            timeout=90,
        )
        collections = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Could not resolve CC indexes from %s (%s) — falling back to the "
            "pinned recent set of %d",
            COLLINFO_URL,
            exc,
            len(_FALLBACK_CC_INDEXES),
        )
        return list(_FALLBACK_CC_INDEXES)

    indexes = []
    for entry in collections:
        cid = entry.get("id", "")
        m = _INDEX_ID_RE.match(cid)
        if m and int(m.group(1)) >= since_year:
            indexes.append(cid)
    if not indexes:
        logger.warning("collinfo.json yielded no indexes since %d", since_year)
        return list(_FALLBACK_CC_INDEXES)
    logger.info("Resolved %d CC indexes since %d", len(indexes), since_year)
    return indexes


def interleave_indexes(indexes: List[str]) -> List[str]:
    """Reorder crawls so a truncated run still spans the whole period.

    ``collinfo.json`` is newest-first, and the fetcher walks the list in order,
    so any source that exhausts its time budget partway through gets only the
    most recent crawls -- a large catalogue ends up with a few months of
    history instead of a decade of it. Bisecting the range repeatedly (ends
    first, then midpoints, then quarter-points) means whatever prefix of the
    list actually runs is spread evenly across time rather than piled at one
    end.
    """
    remaining = list(indexes)
    if len(remaining) <= 2:
        return remaining
    ordered: List[str] = []
    segments = [(0, len(remaining) - 1)]
    ordered.append(remaining[0])
    ordered.append(remaining[-1])
    while segments:
        lo, hi = segments.pop(0)
        mid = (lo + hi) // 2
        if mid not in (lo, hi):
            ordered.append(remaining[mid])
            segments.append((lo, mid))
            segments.append((mid, hi))
    seen = set()
    return [i for i in ordered if not (i in seen or seen.add(i))]


@lru_cache(maxsize=1)
def all_cc_configs() -> Dict[str, Dict[str, str]]:
    """Return ``{spider: {"prefix", "path_re"}}`` for every manifest with a scope.

    A spider served by several manifests takes the first scope encountered in
    manifest-discovery order; the scope is a property of the storefront, not of
    the country the manifest files it under.
    """
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: Dict[str, Dict[str, str]] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception as exc:
            logger.debug("Skipping unloadable manifest %s: %s", path, exc)
            continue
        if not (cfg.spider and cfg.archive_prefix):
            continue
        out.setdefault(
            cfg.spider,
            {"prefix": cfg.archive_prefix, "path_re": cfg.archive_path_re or ""},
        )
    return out


def get_cc_config(spider: str) -> Optional[Dict[str, str]]:
    """Return one spider's archive scope, or None when no manifest declares it."""
    return all_cc_configs().get(spider)
