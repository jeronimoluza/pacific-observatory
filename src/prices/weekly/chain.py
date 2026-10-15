"""`prices weekly run` (PX-35): the registered steps in weekly order, each gated on the one before.

A step starts only when the step before it in ORDER ended DONE for the same week: in
this run, or, for the first step of a `--from` run, in an earlier one (its
STATUS_<step>). A step that fails or is blocked stops the chain; nothing below it
starts. STATUS_run holds the chain's own line. A step in ORDER that this tree has not
registered (`stage_b` lands from its own branch) blocks the chain where it would run.
"""

from __future__ import annotations

import click

from prices.weekly.guards import (
    FLOOR_FREE_GB,
    START_FREE_GB,
    Refused,
    free_gb,
    require_mounted,
)
from prices.weekly.status import Status
from prices.weekly.step import Context, run_step
from prices.weekly.steps import STEPS

ORDER = ["enrich", "fx", "embed", "score_classify", "stage_b", "build"]


def last_status(c: Context, step: str) -> str:
    f = c.week_dir / f"STATUS_{step}"
    return f.read_text().strip() if f.exists() else "(no STATUS)"


def _done(line: str) -> bool:
    parts = line.split()
    return len(parts) > 1 and parts[1] == "DONE"


def span(first: str, last: str) -> list[str]:
    i, j = ORDER.index(first), ORDER.index(last)
    if i > j:
        raise click.BadParameter(f"--from {first} comes after --to {last}")
    return ORDER[i : j + 1]


def _plan(c: Context, steps: list[str]) -> int:
    click.echo(f"week {c.week}  logs {c.week_dir}  countries {len(c.countries or []) or 'all'}")
    try:
        require_mounted(c.backup_mount)
        mount = "ok"
    except Refused as e:
        mount = f"REFUSES ({e})"
    disks = ", ".join(f"{p} {free_gb(p)}G free" for p in [c.backup_mount, *c.disk_paths] if p.exists())
    click.echo(f"every step: mount {c.backup_mount} {mount}; start >= {START_FREE_GB}G, stop < {FLOOR_FREE_GB}G ({disks})")
    prev = ORDER.index(steps[0])
    if prev:
        before = ORDER[prev - 1]
        line = last_status(c, before)
        click.echo(f"gate {steps[0]}: STATUS_{before} DONE -> {'open' if _done(line) else 'BLOCKED'} ({line})")
    for i, s in enumerate(steps):
        if i:
            click.echo(f"gate {s}: {steps[i - 1]} DONE in this run")
        if s in STEPS:
            run_step(STEPS[s], c)
        else:
            click.echo(f"[dry-run] {s}: NOT REGISTERED in this tree; the chain would stop here")
    return 0


def run_chain(c: Context, first: str, last: str) -> int:
    steps = span(first, last)
    if c.dry_run:
        return _plan(c, steps)
    status = Status(c.week_dir, "run")
    i = ORDER.index(first)
    if i and not _done(last_status(c, ORDER[i - 1])):
        before = ORDER[i - 1]
        status.write("BLOCKED", f"STATUS_{before} is not DONE ({last_status(c, before)}); {first} not started")
        return 1
    status.write("RUNNING", f"{first} -> {last}: {' '.join(steps)}")
    for k, s in enumerate(steps):
        rest = " ".join(steps[k + 1 :]) or "-"
        if s not in STEPS:
            status.write("BLOCKED", f"{s} is not registered in this tree; not started: {s} {rest}")
            return 1
        rc = run_step(STEPS[s], c)
        if rc != 0:
            status.write("FAILED", f"{s} rc={rc} ({last_status(c, s)}); not started: {rest}")
            return rc
        status.event(f"{s} DONE")
    status.write("DONE", f"{first} -> {last}")
    return 0
