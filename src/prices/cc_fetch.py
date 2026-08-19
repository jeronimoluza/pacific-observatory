"""Fetch and parse Common Crawl records from a pre-resolved manifest.

The counterpart to :mod:`prices.cc_resolve`. Everything here works from
``filename``/``offset``/``length``, so this half runs on a machine that has
never seen a ``cluster.idx`` -- no 13 GB cache, no 0.3 GB-per-crawl parse.

Stats and side effects match the index-driven path exactly (same counters, same
per-crawl yield file, same unparseable-page samples), so a source backfilled
either way is indistinguishable downstream.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tqdm import tqdm

from .cc_samples import SampleKeeper

logger = logging.getLogger(__name__)


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records


def run_from_manifest(
    scraper,
    location: Tuple[str, str, str],
    manifest: Path,
    num_workers: int = 8,
) -> Dict[str, Any]:
    """Fetch every record in ``manifest`` that is not already saved.

    Grouped by crawl rather than run flat so per-crawl yield stays measurable:
    a parser broken by a site redesign shows up as a cliff at one crawl, and a
    flat run would average that away exactly as the index-driven path used to.
    """
    records = load_manifest(manifest)
    by_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        by_index[rec.get("cc_index", "unknown")].append(rec)

    stats: Dict[str, Any] = {
        "indexes": len(by_index),
        "indexes_failed": 0,
        "queried": len(records),
        "skipped": 0,
        "parsed": 0,
        "fetch_failed": 0,
        "parse_failed": 0,
        "no_extract": 0,
        "save_failed": 0,
        "capped": 0,
    }

    existing = scraper._existing_hashes(location)
    scraper._samples = SampleKeeper(scraper._items_dir(location).parent / "samples")
    per_index: Dict[str, Dict[str, int]] = {}
    logger.info(
        "manifest %s: %d records across %d crawls, %d already held",
        manifest.name,
        len(records),
        len(by_index),
        len(existing),
    )

    for index in sorted(by_index):
        todo = [
            r
            for r in by_index[index]
            if scraper._record_hash(r["url"], r["timestamp"]) not in existing
        ]
        stats["skipped"] += len(by_index[index]) - len(todo)
        here: Dict[str, int] = {"queried": len(by_index[index])}
        if not todo:
            per_index[index] = here
            continue

        pbar = tqdm(total=len(todo), desc=f"{index} fetch+parse")
        with ThreadPoolExecutor(max_workers=num_workers) as ex:
            futures = {
                ex.submit(scraper._process_one, r, location, index): r for r in todo
            }
            for fut in as_completed(futures):
                outcome = fut.result()
                stats[outcome] = stats.get(outcome, 0) + 1
                here[outcome] = here.get(outcome, 0) + 1
                if outcome == "parsed":
                    existing.add(
                        scraper._record_hash(
                            futures[fut]["url"], futures[fut]["timestamp"]
                        )
                    )
                pbar.update(1)
        pbar.close()
        per_index[index] = here

    scraper._write_index_yield(location, per_index)
    return stats
