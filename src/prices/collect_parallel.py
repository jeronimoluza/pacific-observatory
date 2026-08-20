"""Process-parallel driver behind `prices collect -P N`.

`collect` schedules every matched spider into a single Scrapy reactor, so one
hung source stalls the whole run. At -P N this instead dispatches N detached
single-source children (`collect --country X --source Y -P 1`), which bounds the
blast radius of a hung source to that source and lets a per-source timeout kill
it. Workers hit different domains, so CONCURRENT_REQUESTS_PER_DOMAIN still
holds per site.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from prices.config import PriceSourceConfig
from prices.writers import output_path_for

logger = logging.getLogger(__name__)

MIN_FREE_GB = 10

# A measured runtime must outrank a footprint guess, and footprints are byte
# counts, so the offset has to sit above any plausible directory size.
_MEASURED_OFFSET = 10**12

_DONE_STATUSES = {"ok", "ok_norows"}

RESUME_ALL = "ALL"


class DiskSpaceError(RuntimeError):
    """Raised when free disk is already below the floor at launch."""


class ResumeTargetError(RuntimeError):
    """Raised when --resume names a run that has no status ledger."""


def _pair(m: PriceSourceConfig) -> tuple[str, str]:
    return (m.country, m.source)


def child_command(
    project_root: Path, m: PriceSourceConfig, max_items: int | None
) -> list[str]:
    cmd = [
        sys.executable,
        str(project_root / "run.py"),
        "prices",
        "collect",
        "--country",
        m.country,
        "--source",
        m.source,
        "--parallel",
        "1",
    ]
    if max_items is not None:
        cmd += ["--max-items", str(max_items)]
    return cmd


def _all_ledgers(project_root: Path) -> list[Path]:
    return sorted((project_root / "logs" / "prices").glob("_fullrun_*/status.jsonl"))


def resume_ledgers(project_root: Path, resume) -> list[Path]:
    """Which ledgers `--resume` consults.

    RESUME_ALL means every prior wave, which is only what you want while
    continuing a run that was chunked across ledgers the same day. Weeks-old
    ledgers would otherwise skip sources that are long overdue for a refresh,
    so a run directory (or its status.jsonl) can be named to scope the skip to
    that run alone.
    """
    if resume in (RESUME_ALL, True):
        return _all_ledgers(project_root)
    target = Path(resume)
    if target.is_dir():
        target = target / "status.jsonl"
    if not target.is_file():
        raise ResumeTargetError(f"no status ledger at {target}")
    return [target]


def prior_status(project_root: Path, ledgers=None) -> tuple[set[tuple[str, str]], dict]:
    """Fold ledgers into (already-collected pairs, slowest measured secs)."""
    done: set[tuple[str, str]] = set()
    measured: dict[tuple[str, str], float] = {}
    for ledger in _all_ledgers(project_root) if ledgers is None else ledgers:
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            key = (rec.get("country"), rec.get("source"))
            if rec.get("status") in _DONE_STATUSES:
                done.add(key)
            secs = rec.get("secs")
            if secs:
                measured[key] = max(measured.get(key, 0.0), float(secs))
    return done, measured


def _footprint(path: Path) -> int:
    try:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError:
        return 0


def source_footprints(manifests, data_root: Path) -> dict:
    return {
        _pair(m): _footprint(_observations_path(data_root, m).parent) for m in manifests
    }


def order_sources(manifests, *, measured: dict, sizes: dict) -> list[PriceSourceConfig]:
    """Longest-first, so the known long poles start before the pool drains."""
    known = [v for v in sizes.values() if v]
    median = statistics.median(known) if known else 0

    def cost(m: PriceSourceConfig) -> float:
        key = _pair(m)
        if key in measured:
            return _MEASURED_OFFSET + measured[key]
        return sizes.get(key) or median

    return sorted(manifests, key=cost, reverse=True)


def _observations_path(data_root: Path, m: PriceSourceConfig) -> Path:
    return output_path_for(
        data_root=data_root,
        region=m.region,
        subregion=m.subregion,
        country=m.country,
        source=m.source,
        analytical_role=m.analytical_role,
    )


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "rb") as fh:
        lines = sum(1 for _ in fh)
    return max(0, lines - 1)


def _terminate(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), 15)
    except OSError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass


def _collect_one(m, *, project_root, data_root, run_dir, timeout, max_items) -> dict:
    log_path = run_dir / f"{m.country}__{m.source}.log"
    before = _row_count(_observations_path(data_root, m))
    started = time.time()
    status, rc = "ok", 0

    try:
        with open(log_path, "wb") as fh:
            proc = subprocess.Popen(
                child_command(project_root, m, max_items),
                cwd=project_root,
                stdout=fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                status, rc = "timeout", -9
    except OSError as exc:
        status, rc = "runner_error", -1
        with open(log_path, "a") as fh:
            fh.write(f"\nrunner_error: {exc}\n")

    new_rows = max(0, _row_count(_observations_path(data_root, m)) - before)
    if status == "ok":
        if rc != 0:
            status = "fail"
        elif new_rows == 0:
            status = "ok_norows"

    return {
        "region": m.region,
        "country": m.country,
        "source": m.source,
        "scaffolding": m.scaffolding,
        "status": status,
        "rc": rc,
        "secs": round(time.time() - started, 1),
        "new_rows": new_rows,
        "log": str(log_path),
    }


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 2**30


def run_parallel(
    manifests,
    *,
    workers: int,
    timeout: int,
    project_root: Path,
    data_root: Path,
    resume: bool = False,
    max_items: int | None = None,
) -> Path:
    """Dispatch one child process per source, `workers` at a time.

    Returns the run directory holding status.jsonl plus one log per source.
    """
    project_root = Path(project_root)
    data_root = Path(data_root)

    # Cost ordering always reads every ledger: a stale one may hold the only
    # recorded runtime for a long pole. Only the skip set honours the scope.
    _, measured = prior_status(project_root)
    if resume:
        ledgers = resume_ledgers(project_root, resume)
        done, _ = prior_status(project_root, ledgers=ledgers)
        before = len(manifests)
        manifests = [m for m in manifests if _pair(m) not in done]
        logger.info(
            "resume: skipping %d already-collected source(s) from %d ledger(s)",
            before - len(manifests),
            len(ledgers),
        )

    ordered = order_sources(
        manifests, measured=measured, sizes=source_footprints(manifests, data_root)
    )

    free = _free_gb(project_root)
    if free < MIN_FREE_GB:
        raise DiskSpaceError(
            f"refusing to start: {free:.1f} GiB free is below the {MIN_FREE_GB} GiB floor"
        )

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = project_root / "logs" / "prices" / f"_fullrun_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "status.jsonl"
    status_path.touch()

    logger.info(
        "collect -P %d: %d source(s) | per-source cap %ds | %.1f GiB free | logs: %s",
        workers,
        len(ordered),
        timeout,
        free,
        run_dir,
    )

    pending: queue.Queue = queue.Queue()
    for m in ordered:
        pending.put(m)

    halt = threading.Event()
    write_lock = threading.Lock()
    counter = {"done": 0}

    def record(rec: dict) -> None:
        with write_lock:
            counter["done"] += 1
            with open(status_path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            logger.info(
                "[%d/%d] %s/%s %s (%ss, %d new rows)",
                counter["done"],
                len(ordered),
                rec["country"],
                rec["source"],
                rec["status"],
                rec["secs"],
                rec["new_rows"],
            )

    def worker() -> None:
        while not halt.is_set():
            try:
                m = pending.get_nowait()
            except queue.Empty:
                return
            try:
                record(
                    _collect_one(
                        m,
                        project_root=project_root,
                        data_root=data_root,
                        run_dir=run_dir,
                        timeout=timeout,
                        max_items=max_items,
                    )
                )
            finally:
                pending.task_done()
            if _free_gb(project_root) < MIN_FREE_GB:
                logger.error("halting: free disk fell below %d GiB", MIN_FREE_GB)
                halt.set()

    threads = [
        threading.Thread(target=worker, daemon=True) for _ in range(max(1, workers))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return run_dir


def summarize(run_dir: Path) -> dict:
    counts: dict[str, int] = {}
    rows = 0
    for line in (run_dir / "status.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        rows += rec.get("new_rows") or 0
    return {"counts": counts, "new_rows": rows}
