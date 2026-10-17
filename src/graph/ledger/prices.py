"""Prices runs for the ledger, read-only from a8's disk.

Two kinds of evidence:

- collect ledgers ``<tree>/logs/prices/_fullrun_<ts>/status.jsonl`` (run_id = the dir name):
  status, rc, secs and new_rows per source. The per-source log adds start time (first
  log line), requests (``downloader/request_count`` of the Scrapy stats) and the longest
  stretch without progress (``logstats`` lines whose pages and items did not grow).
  ``weekly`` marks the ledgers listed in ``~/po/logs/weekly/<wk>/ledger_path``.
- raw files on disk, one row per source and ISO week (run_id ``raw:<week>``), counted as
  ``graph.checks.raw_sources`` counts them: spiders by lines of the largest
  ``raw_items/<source>_<YYYYMMDD>_<HHMMSS>.jsonl`` of the week, fetchers by rows of
  ``price_observations.csv`` per week of ``scrape_ts``, the larger of both. Start is the
  file name stamp and end its mtime, trusted only from 2026-06-01 (earlier stamps were
  Mac local time, UTC-3) and only for a plausible duration.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from graph.ledger.store import frame, iso_week, plausible, utc

HOME = Path.home()
LEDGER_GLOBS = [
    "po-worktrees/*/logs/prices/_fullrun_*/status.jsonl",
    "po/logs/prices/_fullrun_*/status.jsonl",
]
WEEKLY_LOGS = HOME / "po/logs/weekly"
DATA_ROOT = HOME / "po/data/prices"
UTC_STAMPS_FROM = datetime(2026, 6, 1, tzinfo=timezone.utc)
STATUS = {
    "ok": "DONE",
    "ok_norows": "ZERO",
    "timeout": "TIMEOUT",
    "fail": "FAIL",
    "runner_error": "FAIL",
    "blocked": "BLOCKED",
    "stalled": "STALLED",
}
_LOG_TS = re.compile(rb"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")
_STATS = re.compile(rb"Crawled (\d+) pages .*scraped (\d+) items")
_REQS = re.compile(rb"'downloader/request_count': (\d+)")
_RUN_TS = re.compile(r"_(\d{8}_\d{6})\.jsonl$")
_DIR_TS = re.compile(r"_fullrun_(\d{8})_(\d{6})")


def ledgers() -> list[Path]:
    return sorted({p for g in LEDGER_GLOBS for p in HOME.glob(g)})


def weekly_ledgers() -> dict[str, str]:
    """ledger path -> ISO week, from every ``<wk>/ledger_path``."""
    out = {}
    for lp in WEEKLY_LOGS.glob("*/ledger_path"):
        for p in lp.read_text().strip().split(","):
            if p:
                out[p] = lp.parent.name
    return out


def _ts(raw: bytes) -> datetime:
    return datetime.strptime(raw.decode(), "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def read_log(path: Path) -> dict:
    """Start, request count and longest no-progress stretch (s) of one collect log."""
    out = {"start": None, "requests": None, "max_stall_s": None}
    if not path.exists():
        return out
    last_progress = last_ts = None
    prev = (-1, -1)
    stall = None
    with open(path, "rb") as fh:
        for line in fh:
            if out["start"] is None:
                m = _LOG_TS.match(line)
                if m:
                    out["start"] = _ts(m[1])
            if b"logstats]" not in line:
                continue
            m, s = _LOG_TS.match(line), _STATS.search(line)
            if not (m and s):
                continue
            last_ts = _ts(m[1])
            cur = (int(s[1]), int(s[2]))
            if last_progress is None or cur[0] > prev[0] or cur[1] > prev[1]:
                if last_progress is not None:
                    stall = max(stall or 0, (last_ts - last_progress).total_seconds())
                last_progress, prev = last_ts, cur
        if last_progress is not None:
            stall = max(stall or 0, (last_ts - last_progress).total_seconds())
        fh.seek(max(0, path.stat().st_size - 65536))
        reqs = _REQS.findall(fh.read())
    out["requests"] = int(reqs[-1]) if reqs else None
    out["max_stall_s"] = stall
    return out


def ledger_rows(ledger: Path, week_of: dict[str, str]) -> list[dict]:
    run_id = ledger.parent.name
    m = _DIR_TS.search(run_id)
    run_start = datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )
    weekly = str(ledger) in week_of
    week = week_of.get(str(ledger)) or iso_week(run_start)
    rows = []
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        log = Path(e["log"]) if e.get("log") else None
        info = (
            read_log(log)
            if log
            else {"start": None, "requests": None, "max_stall_s": None}
        )
        secs = e.get("secs")
        start = info["start"]
        if start is None and log and log.exists() and secs is not None:
            start = utc(log.stat().st_mtime - secs)
        end = utc(start.timestamp() + secs) if start and secs is not None else None
        rows.append(
            {
                "pipeline": "prices",
                "run_id": run_id,
                "region": e.get("region"),
                "country": e.get("country"),
                "source": e.get("source"),
                "week": week,
                "start_utc": start,
                "end_utc": end,
                "duration_s": secs,
                "new_rows": e.get("new_rows"),
                "status": STATUS.get(e.get("status"), str(e.get("status")).upper()),
                "rc": e.get("rc"),
                "requests": info["requests"],
                "max_stall_s": e.get("stall_s", info["max_stall_s"]),
                "weekly": weekly,
                "origin": "ledger",
                "log": str(log) if log else None,
            }
        )
    return rows


def _lines(path: Path) -> int:
    n = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            n += chunk.count(b"\n")
    return n


def _fetcher_weeks(csv_path: Path) -> dict[str, int]:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pcsv

    header = csv_path.open(encoding="utf-8").readline().strip().split(",")
    if "scrape_ts" not in header:
        return {}
    t = pcsv.read_csv(
        csv_path,
        convert_options=pcsv.ConvertOptions(
            include_columns=["scrape_ts"], column_types={"scrape_ts": pa.string()}
        ),
    )
    weeks: dict[str, int] = {}
    for v in pc.value_counts(
        pc.utf8_slice_codeunits(t["scrape_ts"], 0, 10)
    ).to_pylist():
        try:
            wk = iso_week(datetime.fromisoformat(v["values"]))
        except (TypeError, ValueError):
            continue
        weeks[wk] = weeks.get(wk, 0) + v["counts"]
    return weeks


def raw_rows(cache, data_root: Path = DATA_ROOT) -> tuple[list[dict], list[dict]]:
    """Weekly raw rows per source, and the refreshed file cache rows
    (path, size, mtime, lines, weeks_json)."""
    cached = {} if cache is None else {r["path"]: r for r in cache.to_dict("records")}
    new_cache = []

    def counted(p: Path, fn):
        st = p.stat()
        c = cached.get(str(p))
        if c and c["size"] == st.st_size and c["mtime"] == st.st_mtime:
            new_cache.append(c)
            return c
        c = {
            "path": str(p),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "lines": None,
            "weeks_json": None,
        }
        c.update(fn(p))
        new_cache.append(c)
        return c

    rows = []
    for sdir in sorted(data_root.glob("*/*/*/*")):
        if sdir.name.startswith("_") or sdir.parts[-4].startswith("_"):
            continue
        if not (
            (sdir / "raw_items").is_dir() or (sdir / "price_observations.csv").exists()
        ):
            continue
        region, _, country, source = sdir.parts[-4:]
        best: dict[str, dict] = {}
        for f in (sdir / "raw_items").glob("*.jsonl"):
            m = _RUN_TS.search(f.name)
            if not m:
                continue
            start = datetime.strptime(m[1], "%Y%m%d_%H%M%S").replace(
                tzinfo=timezone.utc
            )
            c = counted(f, lambda p: {"lines": _lines(p)})
            wk = iso_week(start)
            if wk not in best or c["lines"] > best[wk]["rows"]:
                end = utc(c["mtime"])
                ok = start >= UTC_STAMPS_FROM
                best[wk] = {
                    "rows": c["lines"],
                    "start": start if ok else None,
                    "end": end if ok else None,
                    "log": str(f),
                }
        csv = sdir / "price_observations.csv"
        if csv.exists():
            c = counted(csv, lambda p: {"weeks_json": json.dumps(_fetcher_weeks(p))})
            for wk, n in json.loads(c["weeks_json"]).items():
                if wk not in best or n > best[wk]["rows"]:
                    best[wk] = {"rows": n, "start": None, "end": None, "log": str(csv)}
        for wk, b in best.items():
            rows.append(
                {
                    "pipeline": "prices",
                    "run_id": f"raw:{wk}",
                    "region": region,
                    "country": country,
                    "source": source,
                    "week": wk,
                    "start_utc": b["start"],
                    "end_utc": b["end"],
                    "duration_s": plausible(b["start"], b["end"]),
                    "new_rows": b["rows"],
                    "status": "DONE" if b["rows"] else "ZERO",
                    "rc": None,
                    "requests": None,
                    "max_stall_s": None,
                    "weekly": None,
                    "origin": "raw_items",
                    "log": b["log"],
                }
            )
    return rows, new_cache


def ingest(known: dict, cache, refresh: bool = False, log=print):
    """(runs frame, cache frame). Ledgers already in the ledger with the same number of
    sources are skipped unless ``refresh``."""
    import pandas as pd

    week_of = weekly_ledgers()
    rows = []
    for ledger in ledgers():
        n = sum(1 for line in ledger.read_text().splitlines() if line.strip())
        if not refresh and known.get(("prices", ledger.parent.name)) == n:
            continue
        got = ledger_rows(ledger, week_of)
        log(
            f"prices {ledger.parent.name}: {len(got)} fuentes ({ledger.parent.parent.parent.parent.name})"
        )
        rows += got
    raw, new_cache = raw_rows(cache)
    log(f"prices raw: {len(raw)} fuente-semanas de {len(new_cache)} archivos")
    return frame(rows + raw), pd.DataFrame(
        new_cache, columns=["path", "size", "mtime", "lines", "weeks_json"]
    )
