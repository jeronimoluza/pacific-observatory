"""`po graph deadman`: rojo when an expected run left no STATUS, or the 5TB / disk is not there.

Expectations come from src/configs/notify.yaml `deadman.expect` (name -> at, grace_hours,
max_hours, status glob); `--expect name@at` overrides `at`. Each alert is sent once
(missing: per expected time; stuck: per STATUS file; mount and disk: per UTC day),
remembered in `deadman.state`.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notify.send import notify
from prices.weekly.guards import Refused, free_gb, require_mounted

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KEEP_DAYS = 14


def last_due(at: str, now: datetime) -> datetime:
    """The latest time <= now matching `daily-HH:MM` or `mon-HH:MM` (UTC)."""
    day, hm = at.rsplit("-", 1)
    h, m = (int(x) for x in hm.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if day == "daily":
        return t if t <= now else t - timedelta(days=1)
    if day not in DAYS:
        raise ValueError(f"{at!r}: day must be daily or one of {DAYS}")
    t -= timedelta(days=(now.weekday() - DAYS.index(day)) % 7)
    return t if t <= now else t - timedelta(days=7)


def _newest(pattern: str) -> tuple[Path, datetime] | None:
    files = [Path(p) for p in glob.glob(os.path.expanduser(pattern))]
    if not files:
        return None
    f = max(files, key=lambda p: p.stat().st_mtime)
    return f, datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)


def check_run(name: str, e: dict, now: datetime) -> tuple[str, str] | None:
    """(alert key, message) when this expectation is red, else None."""
    due = last_due(e["at"], now)
    if now < due + timedelta(hours=e.get("grace_hours", 2)):
        due = last_due(e["at"], due - timedelta(minutes=1))
    newest = _newest(e["status"])
    if newest is None or newest[1] < due:
        seen = (
            f"newest {newest[0]} at {newest[1]:%Y-%m-%dT%H:%MZ}"
            if newest
            else f"no {e['status']}"
        )
        return f"missing:{name}:{due:%Y-%m-%dT%H:%MZ}", (
            f"deadman {name}: no run since {due:%Y-%m-%dT%H:%MZ} ({e['at']} + {e.get('grace_hours', 2)}h grace); {seen}"
        )
    path, mtime = newest
    line = path.read_text().strip()
    parts = line.split()
    if (
        len(parts) > 1
        and parts[1] == "RUNNING"
        and now - mtime > timedelta(hours=e.get("max_hours", 24))
    ):
        return f"stuck:{name}:{path}:{mtime:%Y-%m-%dT%H:%MZ}", (
            f"deadman {name}: RUNNING for over {e.get('max_hours', 24)}h: {path}: {line}"
        )
    return None


def check_host(d: dict, backup_mount: Path, now: datetime) -> list[tuple[str, str]]:
    out = []
    day = f"{now:%Y-%m-%d}"
    try:
        require_mounted(backup_mount)
    except Refused as e:
        out.append((f"mount:{backup_mount}:{day}", f"deadman: {e}"))
    free = free_gb(Path("/"))
    if free < d.get("min_free_gb", 15):
        out.append(
            (
                f"disk:/:{day}",
                f"deadman: / has {free}G free < {d.get('min_free_gb', 15)}G",
            )
        )
    return out


def run_deadman(
    cfg: dict, overrides: dict[str, str], backup_mount: Path | None, echo=print
) -> int:
    d = cfg["deadman"]
    now = datetime.now(timezone.utc)
    expect = {k: dict(v) for k, v in d["expect"].items()}
    for name, at in overrides.items():
        if name not in expect:
            raise ValueError(
                f"--expect {name}: not in deadman.expect ({', '.join(expect)})"
            )
        expect[name]["at"] = at
    reds = check_host(d, backup_mount or Path(d["backup_mount"]), now)
    for name, e in expect.items():
        r = check_run(name, e, now)
        if r:
            reds.append(r)
        else:
            echo(f"verde    {name} ({e['at']})")
    state_path = Path(d["state"]).expanduser()
    sent = json.loads(state_path.read_text()) if state_path.exists() else {}
    for key, msg in reds:
        if key in sent:
            echo(f"rojo     {msg}  (already sent {sent[key]})")
            continue
        echo(f"rojo     {msg}  -> {notify('rojo', msg, cfg)}")
        sent[key] = f"{now:%Y-%m-%dT%H:%M:%SZ}"
    cutoff = f"{now - timedelta(days=KEEP_DAYS):%Y-%m-%dT%H:%M:%SZ}"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({k: v for k, v in sent.items() if v >= cutoff}, indent=1) + "\n"
    )
    return 1 if reds else 0
