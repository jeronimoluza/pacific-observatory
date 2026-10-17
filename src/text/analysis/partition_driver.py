"""Run every text-count partition of the corpus, each in its own MemoryMax scope.

Countries first (largest corpus first, ``-j`` at a time), then subregion and region
aggregates, which read only the country states. A country killed by its MemoryMax is
retried once at ``--retry-mem`` under ~/scratch/heavy.lock (the shared lock for jobs
over 8G). Every partition adds a row to ``--capacity``:
step, country_or_all, wall_s, peak_rss_gb, disk_gb (disk = its state + outputs).

    PYTHONPATH=src python -m text.analysis.partition_driver --tail-start 2026-10-01 --end 2026-10-12
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from src.text.analysis import main as build
from src.text.analysis.partition import country_units

HEAVY_LOCK = Path.home() / "scratch" / "heavy.lock"
CAPACITY_COLUMNS = ["step", "country_or_all", "wall_s", "peak_rss_gb", "disk_gb"]


def _gib(n: str) -> float:
    return float(n[:-1]) * {"G": 1, "M": 1 / 1024}[n[-1]]


def _du_gb(*paths: Path) -> float:
    total = 0
    for p in paths:
        if p.exists():
            total += sum(
                f.stat().st_size
                for f in p.rglob("*")
                if f.is_file() and not f.is_symlink()
            )
    return round(total / 2**30, 4)


def _corpus_bytes(unit: dict) -> int:
    return sum(fp.stat().st_size for fp in unit["news_dirs"])


def run_scoped(
    label: str, args: list[str], mem: str, log_dir: Path
) -> tuple[int, float, float]:
    """One partition in its own scope; returns (rc, wall_s, peak_rss_gb)."""
    log = log_dir / f"{label.replace('/', '__')}.log"
    timing = log.with_suffix(".time")
    cmd = [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit=gtext-{re.sub(r'[^A-Za-z0-9_.-]', '_', label)}-{int(time.time())}",
        "-p",
        f"MemoryMax={mem}",
        "-p",
        "MemorySwapMax=0",
        "/usr/bin/time",
        "-v",
        "-o",
        str(timing),
        sys.executable,
        "-u",
        "-m",
        "text.analysis.partition",
        *args,
    ]
    if _gib(mem) > 8:
        cmd = ["flock", str(HEAVY_LOCK), *cmd]
    env = dict(os.environ, PYTHONPATH=str(build.PROJECT_ROOT / "src"))
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    t = time.time()
    with open(log, "a") as f:
        f.write(
            f"# {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} MemoryMax={mem} {' '.join(args)}\n"
        )
        f.flush()
        rc = subprocess.run(
            cmd, cwd=build.PROJECT_ROOT, env=env, stdout=f, stderr=subprocess.STDOUT
        ).returncode
    wall = time.time() - t
    rss = 0.0
    if timing.exists():
        m = re.search(
            r"Maximum resident set size \(kbytes\): (\d+)", timing.read_text()
        )
        rss = int(m.group(1)) / 2**20 if m else 0.0
    return rc, round(wall, 1), round(rss, 3)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="text.analysis.partition_driver")
    ap.add_argument("--tail-start", required=True)
    ap.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument(
        "--countries",
        default="",
        help="comma list; default every country of the corpus",
    )
    ap.add_argument(
        "--plan",
        type=Path,
        help="stream this signed-off plan into the states of the countries it touches",
    )
    ap.add_argument("--no-aggregates", action="store_true")
    ap.add_argument("-j", "--jobs", type=int, default=3, help="countries at a time")
    ap.add_argument("--mem", default="6G", help="MemoryMax per country partition")
    ap.add_argument(
        "--retry-mem", default="14G", help="MemoryMax of the one retry after a kill"
    )
    ap.add_argument("--agg-mem", default="6G")
    ap.add_argument(
        "--log-dir", type=Path, default=Path.home() / "global" / "text" / "logs"
    )
    ap.add_argument(
        "--capacity",
        type=Path,
        default=Path.home() / "global" / "text" / "reports" / "capacity_text.csv",
    )
    ap.add_argument(
        "--step", default="counts_full", help="the capacity row's step label"
    )
    a = ap.parse_args(argv)

    run_dir = a.log_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    a.capacity.parent.mkdir(parents=True, exist_ok=True)
    new_file = not a.capacity.exists()
    cap = open(a.capacity, "a", newline="")
    w = csv.writer(cap)
    if new_file:
        w.writerow(CAPACITY_COLUMNS)

    names = {c for c in a.countries.split(",") if c} or None
    if a.plan and a.step == "counts_full":
        a.step = "counts_delta"
    if a.plan:
        from src.text.analysis.delta import plan_sources

        names = (names or set(plan_sources(a.plan))) & set(plan_sources(a.plan))
    units = sorted(country_units(names), key=_corpus_bytes, reverse=True)
    print(f"{len(units)} countries, logs {run_dir}", flush=True)
    t0 = time.time()
    failed: list[str] = []
    peak = 0.0

    def one(u: dict) -> None:
        nonlocal peak
        args = [
            "country",
            "--name",
            u["name"],
            "--tail-start",
            a.tail_start,
            "--end",
            a.end,
        ]
        if a.plan:
            args = ["delta", "--plan", str(a.plan), *args[1:]]
        rc, wall, rss = run_scoped(f"country/{u['name']}", args, a.mem, run_dir)
        if rc != 0 and rss >= _gib(a.mem) * 0.9:
            print(
                f"  {u['name']}: rc={rc} at {rss}G, retry at {a.retry_mem}", flush=True
            )
            rc, wall2, rss = run_scoped(
                f"country/{u['name']}", args, a.retry_mem, run_dir
            )
            wall += wall2
        disk = _du_gb(u["cache_dir"], u["output_dir"])
        w.writerow([a.step, u["name"], wall, rss, disk])
        cap.flush()
        peak = max(peak, rss)
        print(
            f"  {u['name']}: rc={rc} {wall}s {rss}G {disk}G ({_corpus_bytes(u) / 2**30:.2f} GiB corpus)",
            flush=True,
        )
        if rc != 0:
            failed.append(u["name"])

    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        list(pool.map(one, units))

    if not a.no_aggregates and (names is None or a.plan):
        subs = sorted(
            {
                (u["cache_dir"].parent.parent.name, u["cache_dir"].parent.name)
                for u in units
            }
        )
        regions = sorted({r for r, _ in subs})
        for r, s in [*subs, *((r, None) for r in regions)]:
            label = f"aggregate/{r}" + (f"/{s}" if s else "")
            args = [
                "aggregate",
                "--region",
                r,
                *(["--subregion", s] if s else []),
                "--tail-start",
                a.tail_start,
            ]
            rc, wall, rss = run_scoped(label, args, a.agg_mem, run_dir)
            out = build.OUTPUT_DIR / r / (s or "") / "_aggregate"
            w.writerow(
                [
                    a.step.replace("counts", "aggregate"),
                    label.split("/", 1)[1],
                    wall,
                    rss,
                    _du_gb(out),
                ]
            )
            cap.flush()
            peak = max(peak, rss)
            print(f"  {label}: rc={rc} {wall}s {rss}G", flush=True)
            if rc != 0:
                failed.append(label)

    w.writerow(
        [
            a.step,
            "all",
            round(time.time() - t0, 1),
            peak,
            _du_gb(build.CACHE_DIR, build.OUTPUT_DIR),
        ]
    )
    cap.close()
    print(
        f"done in {time.time() - t0:.0f}s, peak {peak}G, failed: {', '.join(failed) or 'none'}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
