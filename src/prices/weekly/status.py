"""STATUS_<step> and events.log, in the same one-line format the W42 shell runners wrote.

STATUS_<step> holds the step's latest line (overwritten); events.log gets every line,
prefixed with the step name:

    STATUS_enrich  2026-10-14T14:38:16Z DONE concatenate + prepare rc=0, free 45G
    events.log     2026-10-14T14:38:16Z enrich: DONE concatenate + prepare rc=0, free 45G
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOGS_ROOT = Path.home() / "po" / "logs" / "weekly"


def current_week() -> str:
    return datetime.now(timezone.utc).strftime("%G-W%V")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Status:
    def __init__(self, week_dir: Path, step: str):
        self.week_dir = week_dir
        self.step = step

    def write(self, state: str, msg: str) -> None:
        ts = _ts()
        self.week_dir.mkdir(parents=True, exist_ok=True)
        (self.week_dir / f"STATUS_{self.step}").write_text(f"{ts} {state} {msg}\n")
        with open(self.week_dir / "events.log", "a") as f:
            f.write(f"{ts} {self.step}: {state} {msg}\n")

    def event(self, msg: str) -> None:
        self.week_dir.mkdir(parents=True, exist_ok=True)
        with open(self.week_dir / "events.log", "a") as f:
            f.write(f"{_ts()} {self.step}: {msg}\n")
