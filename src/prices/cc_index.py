"""Common Crawl index lookups via the public S3 ``cluster.idx`` files.

``index.commoncrawl.org`` returns 504 on every query as of 2026-08-18, and the
paged API was never fast even when healthy. The same records are reachable
from ``data.commoncrawl.org``: each collection ships a ``cluster.idx`` — a
sorted map of SURT key -> (cdx shard, byte offset, length) — so one binary
search plus a handful of HTTP Range fetches replaces the whole paging loop.

Two things the API hid and this does not:
- CC canonicalises hosts by dropping a leading ``www.``; a prefix that keeps
  it matches nothing.
- A failed fetch raises instead of yielding zero records, so an outage reads
  as an error rather than as "this site was never crawled".
"""

from __future__ import annotations

import bisect
import gzip
import io
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CC_DATA_BASE = "https://data.commoncrawl.org"

# One cluster.idx is ~100MB and never changes once a collection is published,
# so it is cached on disk and reused across spiders and runs.
#
# The parsed form is held in memory too, but strictly bounded. Parsing one
# index into Python lists costs ~0.25-0.30 GB of RSS, and a backfill walks 103
# of them, so an unbounded dict reaches ~25 GB and takes the machine down --
# which is what it did on a 4 GB Raspberry Pi. The bound costs nothing,
# because a run visits each index exactly once inside a single process: the
# entries were never read back. Reuse across sources comes from the on-disk
# copy, not this.
_CLUSTER_MAX_RESIDENT = 2
_CLUSTER_CACHE: "OrderedDict[str, Tuple[List[str], List[Tuple[str, int, int]]]]" = (
    OrderedDict()
)


def cache_dir(project_root: Optional[Path] = None) -> Path:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    d = project_root / "data" / "prices" / "_cc_index"
    d.mkdir(parents=True, exist_ok=True)
    return d


def surt_prefix(url_prefix: str) -> str:
    """``www.shop.com/product/`` -> ``com,shop)/product``.

    Mirrors CC's SURT canonicalisation, including dropping a leading ``www.``.
    The cdx keys lowercase the path as well as the host, so a prefix carrying
    uppercase (``shop.cosmed.com.tw/SalePage/``) matched nothing until the
    path was lowercased here too.
    """
    host, _, path = url_prefix.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    parts.reverse()
    key = ",".join(parts) + ")"
    path = path.rstrip("/").lower()
    return f"{key}/{path}" if path else key


def _download_cluster(index: str, dest: Path) -> None:
    url = f"{CC_DATA_BASE}/cc-index/collections/{index}/indexes/cluster.idx"
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "--fail",
            "--connect-timeout",
            "60",
            "--max-time",
            "900",
            "--retry",
            "3",
            "--retry-delay",
            "5",
            "-o",
            str(dest),
            url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"cluster.idx download failed for {index}: {result.stderr[:300]}"
        )


def load_cluster(index: str) -> Tuple[List[str], List[Tuple[str, int, int]]]:
    """Return (sorted SURT keys, (shard, offset, length) per key) for ``index``."""
    if index in _CLUSTER_CACHE:
        _CLUSTER_CACHE.move_to_end(index)
        return _CLUSTER_CACHE[index]
    path = cache_dir() / f"cluster_{index}.idx"
    if not path.exists():
        logger.info("fetching cluster.idx for %s", index)
        _download_cluster(index, path)
    keys: List[str] = []
    blocks: List[Tuple[str, int, int]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            try:
                keys.append(parts[0].split(" ")[0])
                blocks.append((parts[1], int(parts[2]), int(parts[3])))
            except ValueError:
                continue
    if not keys:
        raise RuntimeError(f"cluster.idx for {index} parsed to zero blocks")
    _CLUSTER_CACHE[index] = (keys, blocks)
    while len(_CLUSTER_CACHE) > _CLUSTER_MAX_RESIDENT:
        _CLUSTER_CACHE.popitem(last=False)
    return keys, blocks


# data.commoncrawl.org 503s cold objects intermittently. curl's own --retry
# does not cover it: a ranged request that dies mid-transfer exits 56, which is
# not in curl's transient-error set, so the built-in retry never fires.
_BLOCK_ATTEMPTS = 6
_BLOCK_RETRY_SECONDS = 10

# A cdx block is ~240 KB and takes about a second, but the connection sometimes
# establishes and then stalls at the TCP layer rather than failing -- measured
# at 2.5 minutes and still running while an independent fetch of the same range
# finished in 1.0 s. --connect-timeout does not cover it, because the connect
# succeeded; only a throughput floor does. Aborting a transfer that spends 20 s
# under 10 KB/s turns a five-minute hang into a twenty-second one, and the
# retry then usually lands on a healthy connection.
_BLOCK_MIN_BYTES_PER_SEC = "10000"
_BLOCK_STALL_SECONDS = "20"
_BLOCK_MAX_SECONDS = "120"


def _fetch_block(index: str, shard: str, offset: int, length: int) -> str:
    url = f"{CC_DATA_BASE}/cc-index/collections/{index}/indexes/{shard}"
    last_err = b""
    for attempt in range(1, _BLOCK_ATTEMPTS + 1):
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--fail",
                "--connect-timeout",
                "20",
                "--max-time",
                _BLOCK_MAX_SECONDS,
                "--speed-limit",
                _BLOCK_MIN_BYTES_PER_SEC,
                "--speed-time",
                _BLOCK_STALL_SECONDS,
                "--retry",
                "3",
                "--retry-delay",
                "5",
                "--retry-all-errors",
                "-r",
                f"{offset}-{offset + length - 1}",
                url,
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            break
        last_err = result.stderr
        if attempt < _BLOCK_ATTEMPTS:
            time.sleep(_BLOCK_RETRY_SECONDS * attempt)
    if result.returncode != 0:
        raise RuntimeError(
            f"cdx block fetch failed after {_BLOCK_ATTEMPTS} attempts "
            f"({index} {shard} @{offset}): "
            f"{last_err[:200].decode('utf-8', 'replace')}"
        )
    return (
        gzip.GzipFile(fileobj=io.BytesIO(result.stdout))
        .read()
        .decode("utf-8", "replace")
    )


def query_prefix(
    index: str,
    url_prefix: str,
    path_re: re.Pattern,
    *,
    max_blocks: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """All status-200 records under ``url_prefix`` whose path matches ``path_re``.

    Returns the same record shape the old index-API path produced:
    ``{url, timestamp, filename, offset, length, digest}``.

    ``max_blocks`` bounds how many cdx blocks are scanned. It defaults to
    unlimited because a bound here truncates *enumeration* -- the URLs beyond
    it are never discovered, so nothing downstream can tell they existed, and
    the warning it logs is the only trace. A source whose prefix spans many
    blocks is exactly the source with the most history to recover.
    """
    keys, blocks = load_cluster(index)
    key = surt_prefix(url_prefix)
    stop = key + "\xff"

    start = max(0, bisect.bisect_right(keys, key) - 1)
    records: List[Dict[str, Any]] = []
    scanned = 0
    pos = start
    while pos < len(keys) and (max_blocks is None or scanned < max_blocks):
        if keys[pos] > stop:
            break
        shard, offset, length = blocks[pos]
        for line in _fetch_block(index, shard, offset, length).split("\n"):
            if not line.startswith(key):
                continue
            # cdx line: "<surt> <timestamp> <json>" — the capture timestamp is
            # the second field, NOT a key inside the JSON payload.
            fields = line.split(" ", 2)
            if len(fields) < 3:
                continue
            try:
                payload = json.loads(fields[2])
            except json.JSONDecodeError:
                continue
            if payload.get("status") != "200":
                continue
            url = payload.get("url", "")
            try:
                if not path_re.search(urlparse(url).path):
                    continue
            except ValueError:
                continue
            try:
                rec_offset = int(payload["offset"])
                rec_length = int(payload["length"])
            except (KeyError, ValueError):
                continue
            records.append(
                {
                    "url": url,
                    "timestamp": fields[1],
                    "filename": payload.get("filename", ""),
                    "offset": rec_offset,
                    "length": rec_length,
                    "digest": payload.get("digest", ""),
                }
            )
        scanned += 1
        pos += 1

    if max_blocks is not None and scanned >= max_blocks:
        logger.warning(
            "%s: stopped at max_blocks=%d for %s — more records may exist "
            "beyond the %d kept",
            index,
            max_blocks,
            url_prefix,
            len(records),
        )
    logger.info(
        "%s: %d product records from %d cdx block(s) (prefix=%s)",
        index,
        len(records),
        scanned,
        url_prefix,
    )
    return records
