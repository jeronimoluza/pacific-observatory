"""The 5TB mount check and the one disk gate every weekly step goes through.

One gate replaces the thresholds the W42 runners carried separately:

    collect.sh           GATE_GB=15 to start, FLOOR_GB=3 watchdog
    collect_parallel.py  MIN_FREE_GB=5 to start and mid-run (ARCHITECTURE.md still says 10)
    cc_devset.py         10 GiB
    w42_stageb           3G per country
    w42_score/chain.sh   4G after each classify

A step refuses to start below START_FREE_GB and is stopped below FLOOR_FREE_GB, on
every disk it writes to. Above ALERT_USED_PCT used, it runs but logs an ALERT.
GiB, like `df -BG`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

START_FREE_GB = 15
FLOOR_FREE_GB = 5
ALERT_USED_PCT = 85
BACKUP_MOUNT = Path("/mnt/backup5tb")


class Refused(Exception):
    pass


def require_mounted(path: Path) -> None:
    # No fstab entry for the 5TB yet (PX-03): unmounted, its path is a plain
    # directory on `/`, and a step writing there fills the root disk.
    try:
        rc = subprocess.run(
            ["findmnt", "-n", "--mountpoint", str(path)], capture_output=True
        ).returncode
    except FileNotFoundError:
        rc = -1
    if rc != 0:
        raise Refused(
            f"{path} is not mounted (findmnt rc={rc}); mount the 5TB first, "
            f"refusing so nothing is written to /"
        )


def free_gb(path: Path) -> int:
    return shutil.disk_usage(path).free // 2**30


def used_pct(path: Path) -> int:
    u = shutil.disk_usage(path)
    return -(-100 * u.used // (u.used + u.free))


def disk_gate(paths: list[Path]) -> list[str]:
    """Refuse below START_FREE_GB on any path; return the 85% alerts."""
    alerts = []
    for p in paths:
        free = free_gb(p)
        if free < START_FREE_GB:
            raise Refused(f"disk {p} {free}G free < gate {START_FREE_GB}G")
        pct = used_pct(p)
        if pct >= ALERT_USED_PCT:
            alerts.append(f"disk {p} {pct}% used >= {ALERT_USED_PCT}%, {free}G free")
    return alerts


def below_floor(paths: list[Path]) -> str | None:
    for p in paths:
        free = free_gb(p)
        if free < FLOOR_FREE_GB:
            return f"disk {p} {free}G free < floor {FLOOR_FREE_GB}G"
    return None
