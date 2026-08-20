"""Sequential Common Crawl backfill over every archive-scoped source.

Replaces the pair of shell + python scripts this ran under previously, which
hardcoded one machine's absolute paths, truncated their own results file on
restart, and dropped the counter that reports lost historical depth.

Design notes that are not obvious from the code:

- **Resume is by reading, not by truncating.** The results file is append-only
  and a source already recorded as ``completed`` is skipped. Restarting is
  therefore free; the previous driver re-enumerated all 623 from scratch.
- **Rows are counted from disk, not from the stats.** ``parsed`` counts
  *pages*, and one page yields anywhere from one row to forty. Counting the
  item files before and after is the only honest measure of what a source
  actually contributed.
- **Concurrency, not request rate, is what gets an IP banned by CC.** Workers
  stay at 8 and the loop is sequential across sources for that reason; do not
  parallelise this by running two copies.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from prices.tools.cc_backfill_state import (
    _PARKED_REASONS,
    _free_gb,
    _free_inodes,
    _last_records,
    _should_run,
)


def _repo_root() -> Path:
    # src/prices/tools/cc_backfill_run.py -> repo root is four parents up.
    return Path(__file__).resolve().parents[3]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _items_dir(root: Path, src) -> Path:
    return (
        root
        / "data"
        / "prices"
        / src.region
        / src.subregion
        / src.country
        / src.spider
        / "common_crawl_data"
        / "items"
    )


def _count_items(path: Path) -> int:
    from prices.cc_storage import count_rows

    return count_rows(path)


def _count_samples(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*/*.html"))


def _resolve_indexes_once(work: Path, since: int) -> List[str]:
    """Resolve the crawl list once, then pin it for every later run.

    collinfo.json 504s intermittently, and the library's fallback is 8 recent
    crawls against the ~123 a full backfill needs. Falling back mid-sweep would
    quietly convert "all the history we can get" into "the last few months",
    with the run still reporting success. So: resolve strictly, write the list
    down, and reuse the file afterwards -- which also makes the set identical
    across machines and across resumes.
    """
    from prices.cc_config import resolve_cc_indexes

    pinned = work / f"indexes_since_{since}.txt"
    if pinned.exists():
        names = [
            ln.strip() for ln in pinned.read_text("utf-8").splitlines() if ln.strip()
        ]
        if names:
            return names
    names = resolve_cc_indexes(since, strict=True)
    work.mkdir(parents=True, exist_ok=True)
    pinned.write_text("\n".join(names) + "\n", encoding="utf-8")
    return names


def _run_one(
    src,
    root: Path,
    log_dir: Path,
    workers: int,
    since: int,
    cap: int,
    indexes: List[str],
    max_per_index: Optional[int],
    manifest_dir: Optional[Path],
) -> Dict:
    from prices.tools import cc_triage

    log_path = log_dir / f"{src.spider}.log"
    py = root / ".venv" / "bin" / "python"
    cmd = [
        str(py) if py.exists() else sys.executable,
        "run.py",
        "prices",
        "common-crawl",
        "-s",
        src.spider,
        "-c",
        src.country,
        "--workers",
        str(workers),
        "--since",
        str(since),
        "--interleave",
    ]
    # A manifest replaces index resolution wholesale: no cluster.idx is read,
    # so this path runs on a machine that cannot hold the 13 GB index cache.
    manifest = (manifest_dir / f"{src.spider}.jsonl") if manifest_dir else None
    if manifest and manifest.exists():
        cmd += ["--manifest", str(manifest)]
    else:
        if manifest_dir:
            return {
                "spider": src.spider,
                "country": src.country,
                "region": src.region,
                "status": "error",
                "verdict": "NO_MANIFEST",
                "flags": ["NO_MANIFEST"],
                "rows_written": 0,
                "rows_total": _count_items(_items_dir(root, src)),
                "yield": 0.0,
                "elapsed_sec": 0.0,
                "stats": {},
                "cliff": {},
                "samples": 0,
                "stop_reason": "",
                "stopped_at": "",
                "covered_through": "",
                "indexes_walked": 0,
                "n_403": 0,
                "n_503": 0,
                "finished_at": _now(),
                "log": "",
            }
        if max_per_index:
            cmd += ["--max-per-index", str(max_per_index)]
        for idx in indexes:
            cmd += ["--index", idx]

    items = _items_dir(root, src)
    rows_before = _count_items(items)

    start = time.time()
    status = "completed"
    text = ""
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, timeout=cap or None
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if proc.returncode != 0:
            status = "error"
    except subprocess.TimeoutExpired as exc:
        status = "timeout"

        def _s(x):
            if x is None:
                return ""
            return x.decode("utf-8", "replace") if isinstance(x, bytes) else x

        text = _s(exc.stdout) + "\n" + _s(exc.stderr)
    except Exception as exc:  # noqa: BLE001 - a broken invocation must not kill the sweep
        status = "error"
        text = f"driver could not run the command: {exc!r}\ncmd: {cmd}"
    elapsed = time.time() - start

    log_path.write_text(text, encoding="utf-8")

    stats = cc_triage.parse_stats(text)
    rows_after = _count_items(items)
    primary, flags = cc_triage.classify(status, stats)

    # A parser that broke at a redesign parses recent crawls fine, so the
    # summed counters call it healthy. The per-crawl file is the only place
    # that boundary is visible.
    cliff: Dict = {}
    yield_file = items.parent / "index_yield.json"
    if yield_file.exists():
        try:
            cliff = cc_triage.date_cliff(json.loads(yield_file.read_text("utf-8")))
        except (OSError, ValueError):
            cliff = {}
    if cliff:
        flags.append("DATE_CLIFF")
        if primary == "OK":
            primary = "DATE_CLIFF"

    # Why the fetch stopped, read from disk rather than scraped from stdout:
    # the distinction between "walked the whole manifest" and "hit a guard" is
    # what the resume decision turns on, and a stdout format change would
    # silently turn every parked source into a finished one.
    fstate: Dict = {}
    state_file = items.parent / "fetch_state.json"
    if manifest_dir and state_file.exists():
        try:
            fstate = json.loads(state_file.read_text("utf-8"))
        except (OSError, ValueError):
            fstate = {}
    reason = str(fstate.get("stop_reason", ""))
    if reason:
        flags.append(reason.upper())
        if primary == "OK":
            primary = reason.upper()

    return {
        "spider": src.spider,
        "country": src.country,
        "region": src.region,
        "status": status,
        "verdict": primary,
        "flags": flags,
        "rows_written": rows_after - rows_before,
        "rows_total": rows_after,
        "yield": round(cc_triage.yield_ratio(stats), 4),
        "elapsed_sec": round(elapsed, 1),
        "stats": stats,
        "cliff": cliff,
        "samples": _count_samples(items.parent / "samples"),
        "stop_reason": reason,
        "stopped_at": fstate.get("stopped_at", ""),
        "covered_through": fstate.get("covered_through", ""),
        "indexes_walked": fstate.get("indexes_walked", 0),
        "n_403": int(fstate.get("http_403", 0)) or text.count("HTTP 403"),
        "n_503": text.count("HTTP 503"),
        "finished_at": _now(),
        "log": str(log_path),
    }


def _wait_for_unblock(cooldown: int, max_wait: int) -> bool:
    """Sleep until Common Crawl answers this host again, or until fed up."""
    from prices.cc_index import reachable

    waited = 0
    while waited < max_wait:
        print(
            f"    blocked by Common Crawl — waiting {cooldown}s ({waited}s so far)",
            flush=True,
        )
        time.sleep(cooldown)
        waited += cooldown
        if reachable():
            print(f"    unblocked after {waited}s", flush=True)
            return True
    print(
        f"    still blocked after {waited}s; continuing so the sweep records "
        f"what it finds rather than stalling forever",
        flush=True,
    )
    return False


def main(argv: Optional[List[str]] = None) -> int:
    from prices.tools.cc_worklist import build_worklist

    root = _repo_root()
    default_work = root / "data" / "prices" / "_cc_backfill"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", type=Path, default=default_work)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--since",
        type=int,
        default=2013,
        help="earliest crawl year; 2013 is ~123 crawls, 2016 only ~103",
    )
    ap.add_argument(
        "--cap",
        type=int,
        default=14400,
        help="per-source seconds; 0 disables. Not destructive -- a timed-out "
        "source resumes from what it already saved on the next pass.",
    )
    ap.add_argument(
        "--max-per-index",
        type=int,
        default=0,
        help="cap new records per crawl; 0 = unlimited (full history)",
    )
    ap.add_argument("--limit", type=int, default=0, help="stop after N sources")
    ap.add_argument("--only", default="", help="comma-separated spider names")
    ap.add_argument(
        "--manifest-dir",
        type=Path,
        default=None,
        help="fetch from per-source manifests (by_source/) instead of resolving "
        "crawl indexes locally; the machine then needs no cluster.idx cache",
    )
    ap.add_argument("--min-free-gb", type=float, default=2.0)
    ap.add_argument(
        "--min-free-inodes",
        type=int,
        default=200_000,
        help="halt when the filesystem is running out of inodes; one item is "
        "one file, so this is exhausted long before the byte quota on a card "
        "with a fixed inode table",
    )
    ap.add_argument("--cooldown", type=int, default=600, help="seconds after a ban")
    ap.add_argument(
        "--max-ban-wait",
        type=int,
        default=7200,
        help="give up waiting out a block after this many seconds and carry on",
    )
    ap.add_argument(
        "--retry-stopped",
        action="store_true",
        help="also re-run sources parked by a dead_parser / empty_crawls guard; "
        "use after fixing a parser. Already-saved records are skipped by hash, "
        "so a re-run costs only the pages that yielded nothing.",
    )
    ap.add_argument("--list", action="store_true", help="print the worklist and exit")
    args = ap.parse_args(argv)

    work = args.workdir
    log_dir = work / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    results_path = work / "results.jsonl"
    triage_path = work / "needs_attention.tsv"

    sources = build_worklist()
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        sources = [s for s in sources if s.spider in wanted]

    if args.list:
        for s in sources:
            print(f"{s.region}\t{s.country}\t{s.spider}")
        print(f"# {len(sources)} sources", file=sys.stderr)
        return 0

    done = _last_records(results_path)
    horizon = {}
    if args.manifest_dir:
        from prices.cc_resolve import read_horizon

        horizon = read_horizon(args.manifest_dir)
    horizon_oldest = str(horizon.get("oldest", ""))
    pending = [
        s
        for s in sources
        if _should_run(done.get(s.spider), horizon_oldest, args.retry_stopped)
    ]
    parked = [
        s.spider
        for s in sources
        if (done.get(s.spider) or {}).get("stop_reason", "") in _PARKED_REASONS
    ]
    if args.limit:
        pending = pending[: args.limit]

    indexes = [] if args.manifest_dir else _resolve_indexes_once(work, args.since)
    mode = (
        f"manifests from {args.manifest_dir}"
        if args.manifest_dir
        else (f"{len(indexes)} crawl indexes resolved locally")
    )
    if args.manifest_dir:
        mode += (
            f", horizon {horizon.get('newest', '?')}..{horizon_oldest or '?'} "
            f"({horizon.get('count', 0)} crawls)"
        )
    print(
        f"{len(sources)} scoped sources, {len(done)} already recorded, "
        f"{len(pending)} to run, {mode}",
        flush=True,
    )
    if parked and not args.retry_stopped:
        print(
            f"{len(parked)} parked awaiting a parser fix (--retry-stopped to "
            f"include): {', '.join(parked[:8])}"
            f"{' ...' if len(parked) > 8 else ''}",
            flush=True,
        )

    if not triage_path.exists():
        triage_path.write_text(
            "finished_at\tverdict\tspider\tcountry\trows\tyield\tflags\n",
            encoding="utf-8",
        )

    for n, src in enumerate(pending, 1):
        free = _free_gb(work)
        if free < args.min_free_gb:
            print(
                f"STOPPING: {free:.1f} GB free, below --min-free-gb "
                f"{args.min_free_gb}. Move data off this disk and resume.",
                flush=True,
            )
            return 2
        inodes = _free_inodes(work)
        if 0 <= inodes < args.min_free_inodes:
            print(
                f"STOPPING: {inodes:,} inodes free, below --min-free-inodes "
                f"{args.min_free_inodes:,}. There may still be free bytes; "
                f"saves would fail one by one without the byte guard noticing.",
                flush=True,
            )
            return 2

        print(
            f"[{n}/{len(pending)}] {src.region} {src.spider} {src.country} "
            f"({free:.1f} GB free)",
            flush=True,
        )
        rec = _run_one(
            src,
            root,
            log_dir,
            args.workers,
            args.since,
            args.cap,
            indexes,
            args.max_per_index,
            args.manifest_dir,
        )
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

        if rec["verdict"] != "OK":
            with triage_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{rec['finished_at']}\t{rec['verdict']}\t{rec['spider']}\t"
                    f"{rec['country']}\t{rec['rows_written']}\t{rec['yield']}\t"
                    f"{','.join(rec['flags'])}\n"
                )
        note = ""
        if rec["cliff"]:
            c = rec["cliff"]
            note = (
                f"  CLIFF {c['worst_year']}={c['worst_yield']} vs "
                f"{c['best_year']}={c['best_yield']}"
            )
        print(
            f"    {rec['verdict']}  rows={rec['rows_written']}  "
            f"yield={rec['yield']}  samples={rec['samples']}  "
            f"{rec['elapsed_sec']}s{note}",
            flush=True,
        )

        if rec.get("stop_reason") == "cc_403_ban" or rec["n_403"]:
            # Waiting beats continuing. The block is per address and expires on
            # its own -- an IPv4 block cleared inside an hour of rest -- but the
            # previous behaviour walked straight into it source after source,
            # which is how one ban cost 165 sources and 9.7 hours for 5,104
            # rows. Sleeping here is the cheapest thing the sweep can do.
            _wait_for_unblock(args.cooldown, args.max_ban_wait)
        else:
            time.sleep(3)

    print(f"DONE {_now()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
