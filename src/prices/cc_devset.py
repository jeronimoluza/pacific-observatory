"""Hold one source's Common Crawl pages on disk, so its parser can be iterated offline.

Nothing in the pipeline keeps raw HTML: a parser fix is otherwise judged by a
second Common Crawl pass. The dev set fetches a source's records once and keeps
them under ``data/prices/_cc_working/<source>/<crawl>/``, where the ladder can
be re-run over them in seconds.

Two kinds of record go in, both at their WARC address:

- ``sample`` -- up to ``PER_YEAR`` records per crawl-year from a manifest,
  evenly spaced. Never the first N: manifest order is SURT, so a head sample
  is one alphabetical corner of the site.
- ``failed`` -- every record a sweep failed to parse (the fleet's ``misses``
  files), so an agent can sort the failures by cause locally.

Records are kept as the raw gzipped WARC record, not bare HTML, so ``decode``
still sees the charset the HTTP headers declare. A per-source byte cap and a
free-disk floor both stop the build; neither is a soft limit. The directory is
gitignored, and ``delete`` is the explicit removal on sign-off.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cc_fetch import load_manifest
from .cc_warc_fetcher import CommonCrawlScraper, get_prices_data_root
from .price_scraping.archived_ladder import parse_rows

logger = logging.getLogger(__name__)

PER_YEAR = 200
CAP_BYTES = 2 * 1024**3
# a8 runs at 97% used; a dev set must never be what fills it.
MIN_FREE_BYTES = 10 * 1024**3
MAX_403 = 40
BATCH = 64


def working_dir(source: str) -> Path:
    return get_prices_data_root() / "_cc_working" / source


def _crawl(rec: Dict[str, Any]) -> str:
    # Manifest records carry ``cc_index``; miss records only the WARC path,
    # whose second segment is the crawl.
    return rec.get("cc_index") or rec["filename"].split("/")[1]


def sample(records: List[Dict[str, Any]], per_year: int = PER_YEAR) -> List[Dict[str, Any]]:
    """Up to ``per_year`` records per crawl-year, evenly spaced across the year."""
    by_year: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        by_year[_crawl(rec)[8:12]].append(rec)
    out: List[Dict[str, Any]] = []
    for year in sorted(by_year):
        recs = sorted(by_year[year], key=lambda r: (_crawl(r), r["url"], r["timestamp"]))
        step = max(len(recs) // per_year, 1)
        out.extend(recs[::step][:per_year])
    return out


def _read_index(root: Path) -> List[Dict[str, Any]]:
    path = root / "index.jsonl"
    return load_manifest(path) if path.exists() else []


def _hold(scraper: CommonCrawlScraper, rec: Dict[str, Any], kind: str, root: Path) -> Optional[Dict[str, Any]]:
    raw = scraper._fetch_warc_record(rec)
    if raw is None:
        return None
    digest = hashlib.sha256(f"{rec['url']}{rec['timestamp']}".encode()).hexdigest()[:16]
    rel = f"{_crawl(rec)}/{rec['timestamp']}_{digest}.warc.gz"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "crawl": _crawl(rec),
        "url": rec["url"],
        "timestamp": rec["timestamp"],
        "file": rel,
        "kind": kind,
        "reason": rec.get("reason", ""),
        "bytes": len(raw),
    }


def build(
    source: str,
    records_path: Path,
    kind: str = "sample",
    per_year: int = PER_YEAR,
    cap_bytes: int = CAP_BYTES,
    workers: int = 8,
) -> Dict[str, Any]:
    """Fetch ``records_path``'s records for ``source`` into its dev set; resumable.

    A record already held is skipped, whatever kind it was held as, so feeding
    a sweep's misses after the sample never fetches a page twice.
    """
    root = working_dir(source)
    root.mkdir(parents=True, exist_ok=True)
    held = _read_index(root)
    have = {(r["url"], r["timestamp"]) for r in held}
    used = sum(r["bytes"] for r in held)

    records = [
        r for r in load_manifest(records_path)
        if (r.get("spider") or r.get("source")) == source
    ]
    todo = sample(records, per_year) if kind == "sample" else sorted(
        records, key=lambda r: (_crawl(r), r["url"], r["timestamp"])
    )
    todo = [r for r in todo if (r["url"], r["timestamp"]) not in have]

    scraper = CommonCrawlScraper(source, root, [])
    stats: Dict[str, Any] = {"records": len(records), "todo": len(todo), "held": 0,
                             "fetch_failed": 0, "stop_reason": ""}
    with open(root / "index.jsonl", "a", encoding="utf-8") as fh, \
            ThreadPoolExecutor(max_workers=workers) as ex:
        for start in range(0, len(todo), BATCH):
            if used >= cap_bytes:
                stats["stop_reason"] = "cap"
            elif shutil.disk_usage(root).free < MIN_FREE_BYTES:
                stats["stop_reason"] = "disk_floor"
            elif scraper.http_403 >= MAX_403:
                stats["stop_reason"] = "cc_403_ban"
            if stats["stop_reason"]:
                break
            batch = todo[start:start + BATCH]
            for row in ex.map(lambda r: _hold(scraper, r, kind, root), batch):
                if row is None:
                    stats["fetch_failed"] += 1
                    continue
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                used += row["bytes"]
                stats["held"] += 1
            fh.flush()
    stats["bytes"] = used
    return stats


def report(source: str) -> Dict[str, Any]:
    """Re-run the ladder over the held records; per-tier hit rates by kind and year.

    Two calls per page: the local one (with the spider's hook) and the fleet
    one (``hook=None``), because they are the two paths a sweep can take.
    """
    root = working_dir(source)
    scraper = CommonCrawlScraper(source, root, [])
    tiers: Dict[str, Counter] = defaultdict(Counter)
    for rec in _read_index(root):
        html = scraper._extract_html_from_record((root / rec["file"]).read_bytes())
        for call, hook in (("local", scraper.parse_html_fn), ("fleet", None)):
            tier = parse_rows(html, rec["url"], source, hook=hook)[1] if html else "undecodable"
            for group in ("all", rec["crawl"][8:12]):
                tiers[f"{rec['kind']}/{call}/{group}"][tier] += 1
    out = {
        key: {"pages": sum(c.values()),
              "share": {t: round(n / sum(c.values()), 4) for t, n in c.most_common()}}
        for key, c in sorted(tiers.items())
    }
    (root / "report.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def delete(source: str) -> None:
    shutil.rmtree(working_dir(source))


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m prices.cc_devset", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="fetch a sample (or, with --failures, every record) into the dev set")
    b.add_argument("source")
    b.add_argument("records", type=Path, help="manifest or misses JSONL")
    b.add_argument("--failures", action="store_true", help="hold every record, not a per-year sample")
    b.add_argument("--per-year", type=int, default=PER_YEAR)
    b.add_argument("--cap-mb", type=int, default=CAP_BYTES // 1024**2)
    b.add_argument("--workers", type=int, default=8)
    sub.add_parser("report", help="re-run the ladder offline; per-tier hit rates").add_argument("source")
    sub.add_parser("delete", help="remove the source's dev set").add_argument("source")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if a.cmd == "build":
        kind = "failed" if a.failures else "sample"
        print(json.dumps(build(a.source, a.records, kind, a.per_year, a.cap_mb * 1024**2, a.workers)))
    elif a.cmd == "report":
        print(json.dumps(report(a.source), indent=1, ensure_ascii=False))
    else:
        delete(a.source)


if __name__ == "__main__":
    main()
