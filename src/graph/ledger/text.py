"""Text runs for the ledger, read-only from a8's disk.

- staged runs ``<staging_root>/<run_id>/`` (``staged_collect_all.sh`` and the panel):
  ``events_<region>.log`` gives start and end per runner tag ``<country>__<source>``,
  ``<region>/<sub>/<country>/<source>/news.csv`` the new rows (counted as STATUS.md
  counts them, ``graph.observers.text_delta.news_rows``; no folder = 0 rows).
- the pre-staging refreshes ``~/text_collect/logs/refresh_<region>_<ts>_nohup.log``
  (run_id ``refresh-<YYYYMMDD>``): durations and states only, new_rows unknown.

Runner events can be glued to the tail of a tqdm line, so they are searched anywhere in
the log, not only at line start (STATUS.md's ``grep -c '^\\[DONE'`` misses those).
A text ``STUCK`` (no news.csv growth after the selector warning) is FAIL with
``max_stall_s`` = the runner's stall window.
"""

from __future__ import annotations

import re
from pathlib import Path

from graph.ledger.store import frame, iso_week, utc

HOME = Path.home()
STAGING_ROOTS = {"": HOME / "text_staging", "panel/": Path("/mnt/backup5tb/text-panel/staging")}
LEGACY_LOGS = HOME / "text_collect/logs"
STALL_SECONDS = 300
EVENT = re.compile(r"\[(START|DONE|FAIL|TIMEOUT|STUCK)\s*\]\s+(\S+)[^\n@]*@ (\d+)")
RUN_DIR = re.compile(r"^\d{8}T\d{4}Z$")
LEGACY = re.compile(r"^refresh_([a-z]+)_(\d{8})T\d{6}Z_nohup\.log$")
RANK = {"DONE": 0, "FAIL": 1, "STUCK": 2, "TIMEOUT": 3}


def read_events(log: Path) -> dict[str, dict]:
    """tag -> {start, end, state}; the strongest end state wins (TIMEOUT > STUCK > FAIL > DONE)."""
    out: dict[str, dict] = {}
    for m in EVENT.finditer(log.read_text(errors="replace")):
        kind, tag, ts = m[1], m[2], int(m[3])
        e = out.setdefault(tag, {"start": None, "end": None, "state": None})
        if kind == "START":
            e["start"] = ts
        elif e["state"] is None or RANK[kind] >= RANK[e["state"]]:
            e["state"], e["end"] = kind, ts
    return out


def _row(run_id: str, region: str, tag: str, e: dict, rows: int | None, log: Path) -> dict:
    country, _, source = tag.partition("__")
    start, end = utc(e["start"]), utc(e["end"])
    state = e["state"]
    status = {"TIMEOUT": "TIMEOUT", "FAIL": "FAIL", "STUCK": "FAIL"}.get(state)
    if state == "DONE":
        status = "ZERO" if rows == 0 else "DONE"
    return {
        "pipeline": "text", "run_id": run_id, "region": region, "country": country,
        "source": source or country, "week": iso_week(start or end) if (start or end) else None,
        "start_utc": start, "end_utc": end,
        "duration_s": (e["end"] - e["start"]) if e["start"] is not None and e["end"] is not None else None,
        "new_rows": rows, "status": status or "FAIL", "rc": None, "requests": None,
        "max_stall_s": STALL_SECONDS if state == "STUCK" else None, "weekly": None,
        "origin": "events", "log": str(log),
    }


def staged_rows(run_dir: Path, run_id: str) -> list[dict]:
    from graph.observers.text_delta import news_rows

    rows = []
    for log in sorted(run_dir.glob("events_*.log")):
        region = log.name[len("events_"):-len(".log")]
        staged = {f"{d.parent.name}__{d.name}": d for d in (run_dir / region).glob("*/*/*") if d.is_dir()}
        for tag, e in read_events(log).items():
            if e["state"] is None:
                continue
            news = staged[tag] / "news.csv" if tag in staged else None
            n = news_rows(news) if news else 0
            rows.append(_row(run_id, region, tag, e, n, log))
    return rows


def legacy_rows(log: Path) -> list[dict]:
    m = LEGACY.match(log.name)
    run_id = f"refresh-{m[2]}"
    return [_row(run_id, m[1], tag, e, None, log) for tag, e in read_events(log).items() if e["state"]]


def ingest(known: dict, refresh: bool = False, log=print):
    rows = []
    for prefix, root in STAGING_ROOTS.items():
        if not root.is_dir():
            continue
        for run_dir in sorted(p for p in root.iterdir() if p.is_dir() and RUN_DIR.match(p.name)):
            run_id = prefix + run_dir.name
            if not (run_dir / ".done").exists():
                log(f"text {run_id}: sin .done, se saltea")
                continue
            if not refresh and ("text", run_id) in known:
                continue
            got = staged_rows(run_dir, run_id)
            log(f"text {run_id}: {len(got)} fuentes")
            rows += got
    by_run: dict[str, list[dict]] = {}
    for f in sorted(LEGACY_LOGS.glob("refresh_*_nohup.log")):
        if LEGACY.match(f.name):
            for r in legacy_rows(f):
                by_run.setdefault(r["run_id"], []).append(r)
    for run_id, got in by_run.items():
        if refresh or ("text", run_id) not in known:
            log(f"text {run_id}: {len(got)} fuentes (sin filas)")
            rows += got
    return frame(rows)
