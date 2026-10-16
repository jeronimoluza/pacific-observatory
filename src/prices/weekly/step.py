"""A weekly step: one command, run in its own `systemd-run --user` scope with a MemoryMax.

`run_step` is the only way a step runs: 5TB mounted, disk gate, RUNNING, the unit, a
floor watchdog, then DONE / FAILED / ABORTED, all through STATUS_<step>.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import click

from prices.weekly.guards import (
    BACKUP_MOUNT,
    Refused,
    below_floor,
    disk_gate,
    free_gb,
    require_mounted,
)
from prices.weekly.status import Status

REPO_ROOT = Path(__file__).resolve().parents[3]
WATCH_SECS = 60


@dataclass
class Context:
    week: str
    logs_root: Path
    countries: list[str] | None = None
    dry_run: bool = False
    backup_mount: Path = BACKUP_MOUNT
    disk_paths: list[Path] = field(default_factory=list)
    # Passed through to the step's runner: `weekly step stage_b -- --out X`.
    extra: tuple[str, ...] = ()

    @property
    def week_dir(self) -> Path:
        return self.logs_root / self.week


@dataclass(frozen=True)
class Step:
    name: str
    memory_max: str
    argv: Callable[[Context], list[str]]
    # Read-only command whose output the dry-run prints (collect: lanes and caps).
    plan: Callable[[Context], list[str]] | None = None
    # Refuse to start when MemAvailable is below memory_max.
    mem_gate: bool = False


def unit_name(step: Step, ctx: Context) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", f"po-weekly-{ctx.week}-{step.name}")


def _unit_active(unit: str) -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", f"{unit}.scope"]
        )
    except FileNotFoundError:
        return False
    return r.returncode == 0


def unit_argv(step: Step, ctx: Context) -> list[str]:
    return [
        "systemd-run",
        "--user",
        "--scope",
        "-q",
        f"--unit={unit_name(step, ctx)}",
        "-p",
        f"MemoryMax={step.memory_max}",
        "-p",
        "MemorySwapMax=1G",
        *step.argv(ctx),
    ]


def _mem_available() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return 0


def _bytes(size: str) -> int:
    return int(float(size[:-1]) * 1024 ** "KMGT".index(size[-1].upper()) * 1024)


def _sha() -> str:
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() or "?"


def run_step(step: Step, ctx: Context) -> int:
    argv = unit_argv(step, ctx)
    unit = unit_name(step, ctx)
    if ctx.dry_run:
        click.echo(f"[dry-run] {step.name}: {' '.join(argv)}")
        if step.plan:
            subprocess.run(step.plan(ctx), cwd=REPO_ROOT)
        return 0
    # cron has no login session: point systemd-run/systemctl --user at the user manager.
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    status = Status(ctx.week_dir, step.name)
    disks = [ctx.backup_mount, *ctx.disk_paths]
    try:
        require_mounted(ctx.backup_mount)
        if _unit_active(unit):
            raise Refused(f"unit {unit}.scope is already active")
        if step.mem_gate and _mem_available() < _bytes(step.memory_max):
            raise Refused(
                f"MemAvailable {_mem_available() / 2**30:.1f}G < MemoryMax={step.memory_max}"
            )
        alerts = disk_gate(disks)
    except Refused as e:
        status.write("BLOCKED", f"{e}; {step.name} not started")
        click.echo(f"BLOCKED {e}", err=True)
        return 1
    for a in alerts:
        status.event(f"ALERT {a}")
    log = ctx.week_dir / f"{step.name}.log"
    status.write(
        "RUNNING",
        f"{' '.join(step.argv(ctx))} @{_sha()}, MemoryMax={step.memory_max}, log {log}",
    )
    with open(log, "a") as out:
        proc = subprocess.Popen(
            argv, cwd=REPO_ROOT, stdout=out, stderr=subprocess.STDOUT
        )
        while True:
            try:
                rc = proc.wait(timeout=WATCH_SECS)
                break
            except subprocess.TimeoutExpired:
                floor = below_floor(disks)
                if floor:
                    # Stopping the scope kills its whole cgroup, children included.
                    subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"])
                    proc.wait()
                    status.write("ABORTED", f"{floor}; {step.name} stopped, log {log}")
                    return 1
    free = free_gb(Path("/"))
    if rc == 0:
        status.write("DONE", f"rc=0, free {free}G")
    else:
        status.write("FAILED", f"rc={rc}, log {log}, free {free}G")
    return rc
