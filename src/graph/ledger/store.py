"""The run ledger on disk: one row per (pipeline, run_id, source), as parquet.

Lives in ``PO_LEDGER_DIR`` (default ``/mnt/backup5tb/po-ledger``): ``runs.parquet`` (the
ledger), ``source_budgets.parquet`` (derived) and ``raw_files.parquet`` (a cache of line
counts of prices raw files, keyed by path + size + mtime, so a re-ingest reads only new
files). Writes are tmp + ``os.replace``. Appending is idempotent per run_id: the rows
of a run_id that is ingested again replace the old ones.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

LEDGER_DIR = Path(os.environ.get("PO_LEDGER_DIR", "/mnt/backup5tb/po-ledger"))
RUNS = "runs.parquet"
BUDGETS = "source_budgets.parquet"
RAW_CACHE = "raw_files.parquet"

# status: DONE (rows > 0, or rows unknown), ZERO (finished with 0 rows), TIMEOUT (killed by
# the wall-clock cap), FAIL (non-zero exit, or text STUCK), BLOCKED (prices blocklist; the
# source was not run). origin: where the row came from.
COLUMNS = {
    "pipeline": "string", "run_id": "string", "region": "string", "country": "string",
    "source": "string", "week": "string", "start_utc": "datetime64[us, UTC]",
    "end_utc": "datetime64[us, UTC]", "duration_s": "float64", "new_rows": "Int64",
    "status": "string", "rc": "Int64", "requests": "Int64", "max_stall_s": "float64",
    "weekly": "boolean", "origin": "string", "log": "string",
}


def iso_week(d: date | datetime) -> str:
    return d.strftime("%G-W%V")


def week_monday(week: str) -> datetime:
    y, w = week.split("-W")
    return datetime.combine(date.fromisocalendar(int(y), int(w), 1), datetime.min.time(), timezone.utc)


def utc(ts: float | None) -> datetime | None:
    return datetime.fromtimestamp(ts, timezone.utc) if ts is not None else None


def frame(rows: list[dict]):
    import pandas as pd

    df = pd.DataFrame(rows, columns=list(COLUMNS))
    for c, t in COLUMNS.items():
        df[c] = pd.to_datetime(df[c], utc=True) if t.startswith("datetime") else df[c].astype(t)
    return df


def read(name: str = RUNS, ledger_dir: Path = LEDGER_DIR):
    import pandas as pd

    path = ledger_dir / name
    return pd.read_parquet(path) if path.exists() else None


def write(df, name: str, ledger_dir: Path = LEDGER_DIR) -> Path:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / name
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return path


def append_runs(new, ledger_dir: Path = LEDGER_DIR) -> tuple[int, int]:
    """Replace the rows of every (pipeline, run_id) in ``new``; returns (replaced, total)."""
    import pandas as pd

    old = read(RUNS, ledger_dir)
    replaced = 0
    if old is not None and len(new):
        keys = set(zip(new["pipeline"], new["run_id"]))
        hit = [k in keys for k in zip(old["pipeline"], old["run_id"])]
        replaced = sum(hit)
        old = old[[not h for h in hit]]
    out = new if old is None or not len(old) else pd.concat([old, new], ignore_index=True)
    out = out.sort_values(["pipeline", "run_id", "country", "source"], ignore_index=True)
    write(out, RUNS, ledger_dir)
    return replaced, len(out)


def known_runs(ledger_dir: Path = LEDGER_DIR) -> dict[tuple[str, str], int]:
    """(pipeline, run_id) -> rows already in the ledger."""
    old = read(RUNS, ledger_dir)
    if old is None:
        return {}
    return old.groupby(["pipeline", "run_id"]).size().to_dict()


def plausible(start: datetime | None, end: datetime | None, max_h: float = 48) -> float | None:
    if start is None or end is None:
        return None
    d = (end - start).total_seconds()
    return d if 0 <= d <= max_h * 3600 else None
