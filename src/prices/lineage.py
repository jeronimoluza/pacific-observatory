"""Where rows go when they stop.

Every stage in this pipeline filters, and until this module every filter reported
its count to a log line and then forgot it. The counts were real -- concatenate
knows exactly how many out-of-stock rows it skipped, build knows how many rows
failed the unit filter -- but they lived for the length of one terminal scrollback
and were never comparable across runs. "The corpus lost four million rows
somewhere between Tuesday and Thursday" was not an answerable question.

It is answerable with two things: a run identifier, which did not exist anywhere
in `src/prices` before this, and one append per filter.

Deliberately not a database. A counter row is ~120 bytes and a run emits a couple
of hundred of them, so the whole history of every run costs less than a single
parquet row group. Keyed drops -- the rows themselves -- are a different artifact
with a different budget; see `record_keys`.

Nothing here may break a pipeline run. Every public function swallows its own
errors: a missing lineage row is a lost diagnostic, a raised one is a lost
overnight sweep.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
LINEAGE_DIR = REPO_ROOT / "data" / "prices" / "_lineage"

ENV_RUN_ID = "PO_PRICES_RUN_ID"
ENV_OFF = "PO_PRICES_NO_LINEAGE"


def enabled() -> bool:
    return os.environ.get(ENV_OFF, "").strip().lower() in ("", "0", "false", "no", "off")


def run_id() -> str:
    """This run's identifier, stable for the life of the process.

    Published into the environment on first use so that pool workers -- which
    fork or spawn from here -- inherit it instead of minting one each. A run
    whose workers disagree about their own identity records four hundred runs
    of one country apiece, which is worse than recording nothing.
    """
    existing = os.environ.get(ENV_RUN_ID)
    if existing:
        return existing
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new = f"{stamp}-{secrets.token_hex(3)}"
    os.environ[ENV_RUN_ID] = new
    return new


def run_dir() -> Path:
    return LINEAGE_DIR / run_id()


def _counter_path() -> Path:
    # One file per process, unioned on read. The alternative is one shared file
    # and a lock, and a lock on the hot path of a 47M-row stage is a trade this
    # does not need to make: a counter is an append of one short line.
    return run_dir() / f"counters-{os.getpid()}.jsonl"


def record(
    stage: str,
    site: str,
    reason: str,
    n_in: Optional[int] = None,
    n_dropped: Optional[int] = None,
    scope: Optional[str] = None,
    **extra,
) -> None:
    """Append one counter.

    `site` is the code location the drop happened at, as `module.py:line` or a
    stable short name -- it is what makes two runs comparable, so it must not be
    a formatted message. `reason` is why. `scope` narrows it to a country,
    source or shard where the caller knows one.
    """
    if not enabled():
        return
    try:
        row = {
            "run_id": run_id(),
            "ts": datetime.now(timezone.utc).isoformat(),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "stage": stage,
            "site": site,
            "reason": reason,
            "n_in": n_in,
            "n_dropped": n_dropped,
            "scope": scope,
        }
        if extra:
            row.update(extra)
        path = _counter_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:  # never take a run down for a diagnostic
        pass


def record_keys(
    stage: str,
    site: str,
    reason: str,
    frame,
    key_cols: Sequence[str] = ("input_hash", "url_hash", "country", "source", "date"),
) -> None:
    """Append the dropped rows themselves, keyed, where the key is in scope.

    Only worth calling where the frame still carries lineage: `url_hash` spans
    concatenate through build, `input_hash` starts at prepare, and
    `build.aggregate.read_observations` projects both away, so downstream of that
    line there is nothing to record and this must not be called.

    Writes parquet per (site, pid) rather than accumulating in memory -- the
    whole point is to survive the runs that are too big to hold.
    """
    if not enabled():
        return
    try:
        if frame is None or len(frame) == 0:
            return
        import pandas as pd  # local: this module is imported by stages that may not need pandas

        cols = [c for c in key_cols if c in frame.columns]
        if not cols:
            record(stage, site, reason, n_dropped=len(frame), scope="no-key-in-scope")
            return
        out = frame.loc[:, cols].copy()
        out["site"] = site
        out["reason"] = reason
        out["run_id"] = run_id()
        safe = site.replace("/", "_").replace(":", "-")
        path = run_dir() / "drops" / f"{stage}-{safe}-{os.getpid()}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            prior = pd.read_parquet(path)
            out = pd.concat([prior, out], ignore_index=True)
        out.to_parquet(path, index=False)
        record(stage, site, reason, n_dropped=len(frame), keyed=True)
    except Exception:
        pass


def read_counters(run: Optional[str] = None):
    """Every counter for a run, newest run by default."""
    import pandas as pd

    root = LINEAGE_DIR / run if run else _latest_run()
    if root is None or not root.is_dir():
        return pd.DataFrame()
    rows = []
    for path in sorted(root.glob("counters-*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return pd.DataFrame(rows)


def _latest_run() -> Optional[Path]:
    if not LINEAGE_DIR.is_dir():
        return None
    runs = sorted(p for p in LINEAGE_DIR.iterdir() if p.is_dir())
    return runs[-1] if runs else None
