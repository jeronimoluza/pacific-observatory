"""Resume decisions and resource guards for the Common Crawl sweep.

Split out of the run loop because both answer the same kind of question --
should this sweep keep going, and with which sources -- and because the loop
itself was over the file-size limit.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional


def _last_records(results_path: Path) -> Dict[str, Dict]:
    """Spider -> the most recent result recorded for it.

    The whole record, not just the status: whether a source should run again
    depends on *why* it stopped and how far the manifest reached at the time,
    and both live in the record.
    """
    out: Dict[str, Dict] = {}
    if not results_path.exists():
        return out
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("spider"):
            out[rec["spider"]] = rec
    return out


# Guards that mean "this source is waiting on a human", not "this source is
# finished". Re-running them unchanged just re-derives the same stop, so they
# stay parked until --retry-stopped says the parser has been looked at.
_PARKED_REASONS = {"dead_parser", "empty_crawls"}


def _should_run(rec: Optional[Dict], horizon_count: int, retry_stopped: bool) -> bool:
    """Whether a source with this prior result is owed another pass."""
    if rec is None:
        return True
    if rec.get("status") != "completed":
        return True
    reason = rec.get("stop_reason", "")
    if reason in _PARKED_REASONS:
        return retry_stopped
    if reason:
        # cc_403_ban and anything else unrecognised: transient, try again.
        return True
    if horizon_count <= 0:
        return False
    # Walked the whole manifest it was given. Owed another pass once the
    # resolve side has published crawls it has not seen -- counted, not
    # compared against the horizon's oldest crawl. The resolver bisects, so
    # the second crawl it ever resolves is already the oldest one there will
    # be: an "is my coverage older than the oldest?" test goes false on pass
    # two and stays false while 116 crawls arrive in the middle, filing every
    # source as finished on a two-crawl manifest and never revisiting it.
    return int(rec.get("horizon_count", 0)) < horizon_count


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def _free_inodes(path: Path) -> int:
    """Free inodes, or -1 where the platform does not report them.

    One item is one small JSON file, so a crawl across the fleet costs roughly
    half a million inodes while costing only a couple of gigabytes. On a card
    formatted with a fixed inode table the inode count runs out first, and it
    runs out *quietly*: df still shows free bytes, the byte guard stays happy,
    and every save starts failing as save_failed while the sweep reports
    progress. Checking bytes alone is not enough.
    """
    try:
        st = os.statvfs(path)
    except (OSError, AttributeError):
        return -1
    return st.f_favail
