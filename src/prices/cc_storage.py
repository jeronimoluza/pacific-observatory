"""On-disk layout for Common Crawl items.

One JSONL per (source, crawl) rather than one JSON per record. Measured on the
fetch machine: 28,989 records were 17 MB of data but **120 MB on disk and
28,989 inodes**, because a ~600-byte file still occupies a 4 KB block. A
fleet-wide crawl is roughly half a million records, so a card with a fixed
inode table ran out after ~8 of 123 crawls while ``df`` still reported free
bytes -- and that failure is silent, because saves start failing one at a time
while the sweep reports progress.

The Wayback half of the archive pipeline already stores ``wayback_items/*.jsonl``,
so this also makes the two halves one shape instead of two.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterator, Set


def record_hash(url: str, timestamp: str) -> str:
    return hashlib.md5(f"{url}#{timestamp}".encode()).hexdigest()


def iter_jsonl(path: Path) -> Iterator[dict]:
    """Rows of a JSONL, skipping anything unreadable.

    A run killed mid-append leaves one partial line. Skipping it costs a single
    re-fetch; refusing to read the file it sits at the end of would cost the
    whole crawl.
    """
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def existing_hashes(items_dir: Path) -> Set[str]:
    """Record hashes already saved, across both storage layouts.

    Legacy one-file-per-record output is still read, so a corpus captured
    before compaction is never re-fetched. The hash is derived from the row
    rather than stored in it: it is exactly what the old filename encoded, so
    both layouts answer the same question with the same key.
    """
    if not items_dir.exists():
        return set()
    out = {f.stem for f in items_dir.glob("*.json")}
    for path in items_dir.glob("*.jsonl"):
        for rec in iter_jsonl(path):
            out.add(record_hash(rec.get("url", ""), rec.get("cc_timestamp", "")))
    return out


def count_rows(items_dir: Path) -> int:
    """Rows held, counting legacy files as one row each."""
    if not items_dir.exists():
        return 0
    n = sum(1 for _ in items_dir.glob("*.json"))
    for path in items_dir.glob("*.jsonl"):
        try:
            with path.open("rb") as fh:
                n += sum(1 for line in fh if line.strip())
        except OSError:
            continue
    return n
