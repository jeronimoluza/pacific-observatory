"""Step `collect` (PX-31): the prices collect of the run's countries, one child per source,
each with its own budget, in two lanes.

- cap per source: its `budget_s` in source_budgets.parquet (`po graph ledger budgets`:
  p95 of the last N timed runs x margin), never below CAP_FLOOR_S nor below the manifest's
  own `timeout:` + the graceful-close grace; a source without history gets DEFAULT_CAP_S;
- stalled: no progress for STALL_MIN minutes (the ledger's rule): neither the Scrapy
  logstats pages/items nor the bytes of the source's new raw files grew; a child that
  never printed logstats (a fetcher) also counts its log growing as progress;
- lanes: a source whose budget is >= SLOW_S (slow on purpose, like the watsons_* behind an
  anti-bot edge, or with no history yet) runs in the slow lane on its own workers, so it
  never holds a fast slot; a long manifest `timeout:` alone only raises the cap. Throttle
  groups still run one member at a time across both lanes;
- over cap or stalled kills that child's process group only (status timeout / stalled);
  every other source keeps going. Each kill goes to `po notify` as it happens.

The ledger is the `collect -P` one, `<run-root>/_fullrun_<ts>/status.jsonl` with a log per
source, plus `lane`, `cap_s` and `stall_s`. It is listed in `<week-dir>/ledger_path` (what
`graph.checks.raw_sources` reads) and appended to the run ledger, whose budgets are then
re-derived. `--plan` prints the lanes and caps and runs nothing.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT
from prices.weekly.steps import _common

SLOW_S = 3600
CAP_FLOOR_S = 900
DEFAULT_CAP_S = 5400
FAST_WORKERS = 16
SLOW_WORKERS = 6
POLL_S = 20
_STATS = re.compile(rb"Crawled (\d+) pages .*scraped (\d+) items")


def _manifests(countries, sources):
    from prices.collect import _load_manifests

    ms = [m for m in _load_manifests(None, None, None, None) if m.active]
    if countries:
        keep = set(countries)
        ms = [m for m in ms if m.country in keep]
    if sources:
        ms = [m for m in ms if m.source in sources or f"{m.country}/{m.source}" in sources]
    return ms


def _budgets() -> dict:
    from graph.ledger.store import BUDGETS, read

    b = read(BUDGETS)
    if b is None:
        return {}
    b = b[b["pipeline"] == "prices"]
    return {(r.country, r.source): r for r in b.itertuples()}


def _overrides(values: list[str]) -> dict[str, float]:
    out = {}
    for v in values:
        k, _, n = v.partition("=")
        out[k] = float(n)
    return out


def plan(ms, budgets: dict, caps: dict, stalls: dict, stall_min: float) -> list[dict]:
    from prices.collect_parallel import SHUTDOWN_GRACE

    rows = []
    for m in ms:
        key = f"{m.country}/{m.source}"
        b = budgets.get((m.country, m.source))
        budget = b.budget_s if b is not None and b.budget_s == b.budget_s else None
        if key in caps:
            cap, why = caps[key], "override"
        else:
            cap = max(budget or DEFAULT_CAP_S, CAP_FLOOR_S, (m.timeout + SHUTDOWN_GRACE) if m.timeout else 0)
            why = "budget" if budget else "default"
        rows.append({
            "m": m, "key": key, "budget_s": budget, "cap_s": int(cap), "cap_from": why,
            "censored": bool(b.censored) if b is not None else False,
            "stall_s": int(stalls.get(key, stall_min) * 60),
            "lane": "slow" if (budget or DEFAULT_CAP_S) >= SLOW_S else "fast",
        })
    return sorted(rows, key=lambda r: r["cap_s"], reverse=True)


def print_plan(rows: list[dict], stall_min: float) -> None:
    from collections import Counter

    print(f"collect plan: {len(rows)} active sources; slow lane = budget >= {SLOW_S}s (or no history); "
          f"cap = max(budget, {CAP_FLOOR_S}s, manifest timeout + grace), {DEFAULT_CAP_S}s without history; "
          f"stalled = {stall_min:g} min without progress")
    for lane, workers in (("fast", FAST_WORKERS), ("slow", SLOW_WORKERS)):
        rs = [r for r in rows if r["lane"] == lane]
        caps = sorted(r["cap_s"] for r in rs)
        src = dict(Counter(r["cap_from"] for r in rs))
        print(f"  lane {lane}: {len(rs)} sources, {workers} workers, cap from {src}, "
              f"censored {sum(r['censored'] for r in rs)}"
              + (f", cap median {caps[len(caps) // 2]}s max {caps[-1]}s, sum {sum(caps) / 3600:.1f} h" if caps else ""))
    for r in [r for r in rows if r["lane"] == "slow"]:
        print(f"    slow {r['key']:48s} cap {r['cap_s']:6d}s ({r['cap_from']}, budget {r['budget_s']})")
    by = Counter(r["m"].country for r in rows)
    print("  per country: " + ", ".join(f"{c} {n}" for c, n in sorted(by.items())))


def _progress(log: Path, files: list[Path], seen_stats: list[bool]) -> tuple:
    """What grows while a child works: last logstats (pages, items), bytes of its raw files,
    and, for a child that never printed logstats (a fetcher), the log's size."""
    stats = (0, 0)
    try:
        with open(log, "rb") as fh:
            fh.seek(max(0, log.stat().st_size - 65536))
            hits = _STATS.findall(fh.read())
        if hits:
            seen_stats[0] = True
            stats = (int(hits[-1][0]), int(hits[-1][1]))
        size = log.stat().st_size
    except OSError:
        size = 0
    raw = 0
    for f in files:
        try:
            raw += f.stat().st_size
        except OSError:
            pass
    return stats, raw, None if seen_stats[0] else size


def collect_one(r: dict, *, run_dir: Path, data_root: Path, max_items, env: dict, on_kill) -> dict:
    from prices import collect_parallel as cp

    m = r["m"]
    log_path = run_dir / f"{m.country}__{m.source}.log"
    items_dir = cp._items_dir(data_root, m)
    csv = cp._observations_path(data_root, m)
    runs_before = cp._run_files(items_dir)
    rows_before = cp._row_count(csv)
    started = last_progress = time.time()
    status, rc, worst = "ok", 0, 0.0
    seen_stats = [False]
    prev = None
    try:
        with open(log_path, "wb") as fh:
            proc = subprocess.Popen(cp.child_command(REPO_ROOT, m, max_items), cwd=REPO_ROOT, env=env,
                                    stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
            while True:
                try:
                    rc = proc.wait(timeout=POLL_S)
                    break
                except subprocess.TimeoutExpired:
                    pass
                now = time.time()
                new = [items_dir / n for n in cp._run_files(items_dir) - runs_before] + [csv]
                cur = _progress(log_path, new, seen_stats)
                if cur != prev:
                    prev, last_progress = cur, now
                worst = max(worst, now - last_progress)
                if now - started > r["cap_s"]:
                    status = "timeout"
                elif now - last_progress > r["stall_s"]:
                    status = "stalled"
                else:
                    continue
                cp._terminate(proc)
                rc = -9
                break
    except OSError as exc:
        status, rc = "runner_error", -1
        with open(log_path, "a") as fh:
            fh.write(f"\nrunner_error: {exc}\n")
    secs = round(time.time() - started, 1)
    new_rows = cp._rows_in_new_runs(items_dir, runs_before) + max(0, cp._row_count(csv) - rows_before)
    if status == "ok":
        if rc != 0:
            status = "fail"
        elif new_rows == 0:
            status = "blocked" if cp._all_blocked(log_path) else "ok_norows"
    rec = {"region": m.region, "country": m.country, "source": m.source, "scaffolding": m.scaffolding,
           "status": status, "rc": rc, "secs": secs, "new_rows": new_rows, "log": str(log_path),
           "lane": r["lane"], "cap_s": r["cap_s"], "stall_s": round(worst, 1)}
    if status in ("timeout", "stalled"):
        on_kill(rec, r)
    return rec


def run_lanes(rows: list[dict], *, run_dir: Path, data_root: Path, max_items, record, on_kill) -> None:
    env = dict(os.environ, PO_DATA_ROOT=str(data_root))
    groups: dict[str, threading.Semaphore] = {}
    guard = threading.Lock()

    def sem(name):
        with guard:
            return groups.setdefault(name, threading.Semaphore(1))

    def worker(q: queue.Queue) -> None:
        while True:
            try:
                r = q.get_nowait()
            except queue.Empty:
                return
            g = sem(r["m"].throttle_group) if r["m"].throttle_group else None
            if g is not None and not g.acquire(blocking=False):
                q.put(r)
                time.sleep(5)
                continue
            try:
                record(collect_one(r, run_dir=run_dir, data_root=data_root, max_items=max_items,
                                   env=env, on_kill=on_kill))
            finally:
                if g is not None:
                    g.release()

    threads = []
    for lane, n in (("fast", FAST_WORKERS), ("slow", SLOW_WORKERS)):
        q: queue.Queue = queue.Queue()
        for r in rows:
            if r["lane"] == lane:
                q.put(r)
        threads += [threading.Thread(target=worker, args=(q,), daemon=True) for _ in range(min(n, q.qsize()))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def to_ledger(status_path: Path, week: str) -> str:
    """Append this run to the run ledger and re-derive the budgets."""
    from graph.ledger import budgets as B
    from graph.ledger import store
    from graph.ledger.prices import ledger_rows

    df = store.frame(ledger_rows(status_path, {str(status_path): week}))
    _, total = store.append_runs(df)
    b = B.derive(store.read(store.RUNS))
    store.write(b, store.BUDGETS)
    return f"ledger +{len(df)} rows ({total} total), budgets {len(b)} sources in {store.LEDGER_DIR}"


def main() -> int:
    from graph.ledger.budgets import STALL_MIN

    ap = _common.parser("collect")
    ap.add_argument("--plan", action="store_true", help="print lanes and caps; run nothing")
    ap.add_argument("--sources", default=None, help="comma-separated source or country/source")
    ap.add_argument("--data-root", type=Path, default=REPO_ROOT / "data")
    ap.add_argument("--run-root", type=Path, default=REPO_ROOT / "logs" / "prices")
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument("--stall-min", type=float, default=STALL_MIN)
    ap.add_argument("--cap", action="append", default=[], help="country/source=SECONDS (test override)")
    ap.add_argument("--stall", action="append", default=[], help="country/source=MINUTES (test override)")
    args = ap.parse_args()
    sources = set(args.sources.split(",")) if args.sources else None
    ms = _manifests(_common.countries(args.countries), sources)
    rows = plan(ms, _budgets(), _overrides(args.cap), _overrides(args.stall), args.stall_min)
    print_plan(rows, args.stall_min)
    if args.plan:
        return 0
    if not rows:
        print("no active sources matched", flush=True)
        return 1

    from notify.send import notify

    status = Status(args.week_dir, "collect")
    run_dir = args.run_root / f"_fullrun_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "status.jsonl"
    status_path.touch()
    args.week_dir.mkdir(parents=True, exist_ok=True)
    lp = args.week_dir / "ledger_path"
    old = [p for p in lp.read_text().strip().split(",") if p] if lp.exists() else []
    lp.write_text(",".join([*old, str(status_path)]) + "\n")
    _common.say(status, f"collect {len(rows)} sources, data {args.data_root}, ledger {status_path}")
    lock = threading.Lock()
    done = {"n": 0, "rows": 0, "by": {}}

    def record(rec: dict) -> None:
        with lock:
            with open(status_path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            done["n"] += 1
            done["rows"] += rec["new_rows"]
            done["by"][rec["status"]] = done["by"].get(rec["status"], 0) + 1
            print(f"[{done['n']}/{len(rows)}] {rec['lane']} {rec['country']}/{rec['source']} {rec['status']} "
                  f"({rec['secs']}s / cap {rec['cap_s']}s, {rec['new_rows']} rows)", flush=True)

    def on_kill(rec: dict, r: dict) -> None:
        why = (f"cap {r['cap_s']}s ({r['cap_from']})" if rec["status"] == "timeout"
               else f"{r['stall_s'] // 60} min without new rows or requests")
        msg = (f"{args.week} collect {rec['country']}/{rec['source']}: {rec['status'].upper()} killed after "
               f"{rec['secs']:.0f}s, {why}; {rec['new_rows']} rows; other sources continue; log {rec['log']}")
        status.event(f"KILLED {msg}")
        try:
            notify("amarillo", msg)
        except Exception as e:  # an alert must never stop the collect it reports on
            print(f"po notify failed: {type(e).__name__}: {e}", file=sys.stderr)

    run_lanes(rows, run_dir=run_dir, data_root=args.data_root, max_items=args.max_items,
              record=record, on_kill=on_kill)
    _common.say(status, f"collect done: {done['by']}, {done['rows']} new rows; ledger {status_path}")
    try:
        _common.say(status, to_ledger(status_path, args.week))
    except Exception as e:  # the collect is done; a ledger write error is reported, not fatal
        _common.say(status, f"ALERT run ledger not updated: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
