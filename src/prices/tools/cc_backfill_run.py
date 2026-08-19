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
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


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
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*.json"))


def _count_samples(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*/*.html"))


def _done_spiders(results_path: Path) -> Dict[str, str]:
    """Spider -> status for every source already recorded."""
    out: Dict[str, str] = {}
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
            out[rec["spider"]] = rec.get("status", "")
    return out


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def _run_one(
    src,
    root: Path,
    log_dir: Path,
    workers: int,
    since: int,
    cap: int,
    indexes: List[str],
    max_per_index: Optional[int],
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
            cmd, cwd=root, capture_output=True, text=True, timeout=cap
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
        "n_403": text.count("HTTP 403"),
        "n_503": text.count("HTTP 503"),
        "finished_at": _now(),
        "log": str(log_path),
    }


def main(argv: Optional[List[str]] = None) -> int:
    from prices.tools.cc_worklist import build_worklist

    root = _repo_root()
    default_work = root / "data" / "prices" / "_cc_backfill"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", type=Path, default=default_work)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--since", type=int, default=2016)
    ap.add_argument("--cap", type=int, default=7200, help="per-source seconds")
    ap.add_argument("--max-per-index", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="stop after N sources")
    ap.add_argument("--only", default="", help="comma-separated spider names")
    ap.add_argument("--min-free-gb", type=float, default=2.0)
    ap.add_argument("--cooldown", type=int, default=600, help="seconds after a ban")
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

    done = _done_spiders(results_path)
    pending = [s for s in sources if done.get(s.spider) != "completed"]
    if args.limit:
        pending = pending[: args.limit]

    from prices.cc_config import resolve_cc_indexes

    indexes = resolve_cc_indexes(args.since)
    print(
        f"{len(sources)} scoped sources, {len(done)} already recorded, "
        f"{len(pending)} to run, {len(indexes)} crawl indexes",
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

        if rec["n_403"] or rec["n_503"] >= 3:
            print(f"    ban signal — cooling down {args.cooldown}s", flush=True)
            time.sleep(args.cooldown)
        else:
            time.sleep(3)

    print(f"DONE {_now()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
