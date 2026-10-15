"""Step `stage_b` (W42 runbook step 12, was ~/scratch/w42_stageb/chain.sh): Stage B, food then nonfood.

Each country runs `prices stage-b-streamed` in its own process, so memory goes back
between countries, and its wall time and peak RSS (wait4's ru_maxrss) are printed.
A country is done when its report.txt and both check csvs exist: done countries are
kept as they are, and the ones still missing after a pass get one more try.

`--as-of` (default: Wednesday of --week, the day W42's FX cache was refreshed) is the
date `require_fresh_fx` measures the cache against, so a past week re-runs as it ran.
After both scopes: countries, rows, trusted and product_months per scope against the
previous week's tree (`--prev`, default stage_b_w<NN-1> on the 5TB).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from prices.weekly.guards import BACKUP_MOUNT
from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT
from prices.weekly.steps import _common

SCOPES = ("food", "nonfood")
DONE_FILES = ("report.txt", "check_ab.csv", "check_imputed.csv")
RETRIES = 1
PREV_ROOT = BACKUP_MOUNT / "po_outputs" / "prices_refactor"


def _week_day(week: str, weekday: int) -> date:
    year, wk = week.split("-W")
    return date.fromisocalendar(int(year), int(wk), weekday)


def _dir(root: Path, country: str, scope: str) -> Path:
    return root / country / ("nonfood" if scope == "nonfood" else "")


def _done(root: Path, country: str, scope: str) -> bool:
    d = _dir(root, country, scope)
    return all((d / f).exists() for f in DONE_FILES)


def _run_one(country: str, scope: str, out: Path, as_of: str) -> int:
    argv = [
        sys.executable,
        "-u",
        str(REPO_ROOT / "run.py"),
        "prices",
        "stage-b-streamed",
        "--country",
        country,
        "--scope",
        scope,
        "--out",
        str(out),
        "--as-of",
        as_of,
    ]
    start = time.time()
    sys.stdout.flush()
    proc = subprocess.Popen(argv, cwd=REPO_ROOT)
    _, st, ru = os.wait4(proc.pid, 0)
    rc = os.waitstatus_to_exitcode(st)
    proc.returncode = rc
    print(
        f"{'DONE' if rc == 0 else 'FAIL'} {scope} {country} rc={rc} "
        f"{time.time() - start:.0f}s maxrss={ru.ru_maxrss / 2**20:.2f}G",
        flush=True,
    )
    return rc


def _scope(
    status: Status, scope: str, countries: list[str], out: Path, as_of: str
) -> list[str]:
    todo = [c for c in countries if not _done(out, c, scope)]
    _common.say(
        status,
        f"{scope} start: {len(todo)} to run, {len(countries) - len(todo)} done and kept",
    )
    for attempt in range(1 + RETRIES):
        for c in todo:
            _run_one(c, scope, out, as_of)
        todo = [c for c in todo if not _done(out, c, scope)]
        if todo and attempt < RETRIES:
            _common.say(status, f"{scope} retry {len(todo)}: {', '.join(todo)}")
    _common.say(
        status, f"{scope} end: {len(countries) - len(todo)}/{len(countries)} done"
    )
    return todo


def _counts(root: Path, countries: list[str], scope: str) -> tuple[int, int, int, int]:
    n = rows = trusted = pm = 0
    for c in countries:
        d = _dir(root, c, scope)
        if not (d / "report.txt").exists():
            continue
        n += 1
        rows += pq.ParquetFile(d / "observations.parquet").metadata.num_rows
        trusted += pq.ParquetFile(d / "trusted_observations.parquet").metadata.num_rows
        pm += pq.ParquetFile(d / "product_months.parquet").metadata.num_rows
    return n, rows, trusted, pm


def _metrics(out: Path, prev: Path, countries: list[str]) -> None:
    names = ("countries", "rows", "trusted", "product_months")
    for scope in SCOPES:
        cur = _counts(out, countries, scope)
        line = " ".join(f"{k}={v:,}" for k, v in zip(names, cur))
        print(f"METRICS {scope:8s} this {line}", flush=True)
        if not prev.is_dir():
            print(f"METRICS {scope:8s} no previous week at {prev}", flush=True)
            continue
        old = _counts(prev, countries, scope)
        line = " ".join(f"{k}={v:,} ({c - v:+,})" for k, v, c in zip(names, old, cur))
        print(f"METRICS {scope:8s} prev {line}  [{prev.name}]", flush=True)


def main() -> int:
    ap = _common.parser("stage_b")
    ap.add_argument(
        "--out", type=Path, default=REPO_ROOT / "outputs" / "prices" / "stage_b"
    )
    ap.add_argument(
        "--as-of", default=None, help="YYYY-MM-DD; default Wednesday of --week"
    )
    ap.add_argument("--prev", type=Path, default=None)
    args = ap.parse_args()
    countries = _common.countries(args.countries)
    if countries is None:
        from prices.enrich.prepare_shards import PREPARED_DIR

        countries = sorted({p.stem for p in _common.prepared_files(PREPARED_DIR, None)})
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    as_of = args.as_of or _week_day(args.week, 3).isoformat()
    prev_week = (_week_day(args.week, 1) - timedelta(days=7)).isocalendar().week
    prev = args.prev or PREV_ROOT / f"stage_b_w{prev_week:02d}"
    status = Status(args.week_dir, "stage_b")
    _common.say(status, f"stage_b {len(countries)} countries -> {out}, as-of {as_of}")
    missing = {}
    for scope in SCOPES:
        missing[scope] = _scope(status, scope, countries, out, as_of)
    _metrics(out, prev, countries)
    failed = [f"{s}:{c}" for s, cs in missing.items() for c in cs]
    if failed:
        _common.say(status, f"FAILED not done after retry: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
