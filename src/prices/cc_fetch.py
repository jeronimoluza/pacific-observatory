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
import threading
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
    stop_after_empty: int = 2,
    min_evidence: int = 20,
    dead_after: int = 300,
    max_403: int = 40,
) -> Dict[str, Any]:
    """Fetch every record in ``manifest`` that is not already saved.

    Grouped by crawl rather than run flat so per-crawl yield stays measurable:
    a parser broken by a site redesign shows up as a cliff at one crawl, and a
    flat run would average that away exactly as the index-driven path used to.

    Crawls are walked **newest first**. The recent end is where a parser
    written against the live site actually matches, so the useful rows arrive
    early and a source that has to be cut short keeps the years most likely to
    be readable rather than the ones least likely.

    Three guards stop a source early, and each records *why* on the returned
    stats -- a backfill has no natural failure signal, so a stop that is not
    written down is indistinguishable from a source that simply had no more
    history:

    - ``dead_parser``  -- ``dead_after`` records attempted, not one row out.
      A parser that never matched this site's markup at all.
    - ``empty_crawls`` -- ``stop_after_empty`` consecutive crawls yielded
      nothing despite each attempting at least ``min_evidence`` records. A
      parser that matched the recent template and stopped at a redesign.
    - ``cc_403_ban``   -- Common Crawl is refusing this IP. Continuing would
      convert a ban into hours of zero-yield work that still reports success.

    A crawl with fewer than ``min_evidence`` records to do is not evidence of
    anything and never increments the streak; that includes a crawl whose
    records are all already held, which on a resume would otherwise look
    identical to a crawl that yielded nothing.
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
        "http_403": 0,
        "attempted": 0,
        "stop_reason": "",
        "stopped_at": "",
        "indexes_walked": 0,
        "covered_through": "",
    }

    existing = scraper._existing_hashes(location)
    scraper._samples = SampleKeeper(scraper._items_dir(location).parent / "samples")
    per_index: Dict[str, Dict[str, int]] = {}
    order = sorted(by_index, reverse=True)
    logger.info(
        "manifest %s: %d records across %d crawls (%s..%s), %d already held",
        manifest.name,
        len(records),
        len(by_index),
        order[0] if order else "-",
        order[-1] if order else "-",
        len(existing),
    )

    empty_streak = 0
    for index in order:
        todo = [
            r
            for r in by_index[index]
            if scraper._record_hash(r["url"], r["timestamp"]) not in existing
        ]
        stats["skipped"] += len(by_index[index]) - len(todo)
        here: Dict[str, int] = {"queried": len(by_index[index]), "todo": len(todo)}
        stats["indexes_walked"] += 1
        stats["covered_through"] = index
        if not todo:
            per_index[index] = here
            continue

        pbar = tqdm(total=len(todo), desc=f"{index} fetch+parse")
        banned = threading.Event()

        def one(rec):
            # The worker reads the 403 counter itself rather than waiting to
            # be stopped from outside. ``Future.cancel`` only stops work that
            # has not started, and a flag set by the consumer arrives late --
            # a queue already draining runs to the end either way.
            if getattr(scraper, "http_403", 0) >= max_403:
                return "aborted"
            return scraper._process_one(rec, location, index)

        with ThreadPoolExecutor(max_workers=num_workers) as ex:
            futures = {ex.submit(one, r): r for r in todo}
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
                # The ban check belongs here, not only at the crawl boundary.
                # A crawl can hold thousands of records: one source spent 29
                # minutes and 20.3k refusals inside a single crawl before the
                # boundary check got its first look. Checking per record turns
                # a half-hour of refusals into seconds of them.
                if not banned.is_set() and getattr(scraper, "http_403", 0) >= max_403:
                    banned.set()
                    logger.warning(
                        "%s: %d x HTTP 403 during %s -- abandoning this crawl",
                        manifest.stem,
                        getattr(scraper, "http_403", 0),
                        index,
                    )
        pbar.close()
        per_index[index] = here
        # Abandoned records were never tried, so counting them as attempts
        # would make a banned source look like a dead parser.
        stats["attempted"] += len(todo) - here.get("aborted", 0)
        stats["http_403"] = getattr(scraper, "http_403", 0)

        stop = _stop_reason(
            stats,
            here,
            len(todo),
            empty_streak,
            stop_after_empty,
            min_evidence,
            dead_after,
            max_403,
        )
        if here.get("parsed", 0) > 0:
            empty_streak = 0
        elif len(todo) >= min_evidence:
            empty_streak += 1
        if stop:
            stats["stop_reason"] = stop
            stats["stopped_at"] = index
            logger.warning(
                "%s: stopping at %s (%s) -- %d crawls walked of %d, %d rows",
                manifest.stem,
                index,
                stop,
                stats["indexes_walked"],
                len(by_index),
                stats["parsed"],
            )
            break

    scraper._write_index_yield(location, per_index)
    _write_fetch_state(scraper, location, stats, len(by_index))
    return stats


def _write_fetch_state(
    scraper, location, stats: Dict[str, Any], n_indexes: int
) -> None:
    """Persist why this source stopped, next to the items.

    On disk rather than on stdout because the sweep driver reads it back to
    decide whether a source is finished or merely paused: a source that walked
    every crawl in its manifest is done until the manifest grows, while one
    that tripped a guard is waiting on a parser fix. Losing that distinction
    is how a source with three years of history gets filed as complete.
    """
    path = scraper._items_dir(location).parent / "fetch_state.json"
    payload = {
        "stop_reason": stats.get("stop_reason", ""),
        "stopped_at": stats.get("stopped_at", ""),
        "covered_through": stats.get("covered_through", ""),
        "indexes_walked": stats.get("indexes_walked", 0),
        "indexes_in_manifest": n_indexes,
        "parsed": stats.get("parsed", 0),
        "http_403": stats.get("http_403", 0),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def _stop_reason(
    stats: Dict[str, Any],
    here: Dict[str, int],
    n_todo: int,
    empty_streak: int,
    stop_after_empty: int,
    min_evidence: int,
    dead_after: int,
    max_403: int,
) -> str:
    """Which guard, if any, has tripped after finishing one crawl."""
    if stats["http_403"] >= max_403:
        return "cc_403_ban"
    if stats["parsed"] == 0 and stats["attempted"] >= dead_after:
        return "dead_parser"
    if (
        here.get("parsed", 0) == 0
        and n_todo >= min_evidence
        and empty_streak + 1 >= stop_after_empty
    ):
        return "empty_crawls"
    return ""
