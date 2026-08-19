"""Resolve Common Crawl records to a manifest, separating index work from fetching.

A backfill has two halves with very different requirements. Resolving which
records exist needs ``cluster.idx`` -- 13 GB on disk for ~123 crawls, and
~0.3 GB of RAM per crawl while parsing. Fetching those records needs neither:
a WARC range request needs only ``filename``, ``offset`` and ``length``.

Splitting them lets the index half run where the 13 GB already sits and the
fetch half run anywhere -- a Raspberry Pi with a 16 GB card, say, which cannot
hold the index set at all. The manifest is small: ~250 bytes per record.

Resolution is **index-major**: each ``cluster.idx`` is loaded once and every
source's prefix is looked up against it, rather than each source re-loading all
123. Source-major costs 623x the parse work and 623x the disk reads of the
same 13 GB -- roughly 8 TB of reads and 15 hours of CPU, for identical output.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

logger = logging.getLogger(__name__)

# Fields the fetch side needs. Anything else is index-side detail.
_RECORD_FIELDS = ("url", "timestamp", "filename", "offset", "length", "digest")


def by_index_dir(root: Path) -> Path:
    return root / "by_index"


def by_source_dir(root: Path) -> Path:
    return root / "by_source"


def resolved_marker(root: Path, index: str) -> Path:
    return by_index_dir(root) / f"{index}.jsonl"


def resolve_index(
    index: str,
    sources: Sequence,
    configs: Dict[str, Dict[str, str]],
    root: Path,
) -> int:
    """Resolve every source against one crawl; write one JSONL, atomically.

    The file is written to a temp name and renamed, so an interrupted run
    leaves either a complete crawl or no crawl -- never a half one that a
    resume would mistake for finished.
    """
    out_dir = by_index_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{index}.jsonl"
    tmp = out_dir / f".{index}.jsonl.tmp"

    from prices.cc_index import query_prefix

    written = 0
    with open(tmp, "w", encoding="utf-8") as fh:
        for src in sources:
            cfg = configs.get(src.spider)
            if not cfg:
                continue
            try:
                records = query_prefix(
                    index, cfg["prefix"], re.compile(cfg["path_re"] or "")
                )
            except Exception as exc:  # noqa: BLE001 - one bad source must not
                # abandon the other 622 already paid for by this crawl's parse.
                logger.warning("%s/%s: resolve failed: %s", index, src.spider, exc)
                continue
            for rec in records:
                row = {k: rec.get(k) for k in _RECORD_FIELDS}
                row["spider"] = src.spider
                row["country"] = src.country
                row["cc_index"] = index
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
    os.replace(tmp, final)
    return written


def resolved_indexes(root: Path) -> List[str]:
    """Crawls already fully resolved, by the presence of their final file."""
    d = by_index_dir(root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.jsonl"))


def iter_records(root: Path) -> Iterable[Dict]:
    for path in sorted(by_index_dir(root).glob("*.jsonl")):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def consolidate(root: Path) -> Dict[str, int]:
    """Regroup the per-crawl files into one manifest per source.

    The fetch side works a source at a time, so shipping it 123 crawl files to
    filter would make every worker read the whole corpus. Counts are returned
    so a caller can report what each source is owed.
    """
    out_dir = by_source_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    handles: Dict[str, object] = {}
    counts: Dict[str, int] = {}
    try:
        for rec in iter_records(root):
            spider = rec.get("spider")
            if not spider:
                continue
            fh = handles.get(spider)
            if fh is None:
                fh = open(out_dir / f".{spider}.jsonl.tmp", "w", encoding="utf-8")
                handles[spider] = fh
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[spider] = counts.get(spider, 0) + 1
    finally:
        for fh in handles.values():
            fh.close()
    for spider in handles:
        os.replace(
            out_dir / f".{spider}.jsonl.tmp",
            out_dir / f"{spider}.jsonl",
        )
    return counts
