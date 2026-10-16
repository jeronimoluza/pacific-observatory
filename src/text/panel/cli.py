"""`po text panel`: the text chain over a country panel, collect -> merge (a plan) -> AWAITING_SIGNOFF,
then `signoff <run_id>` -> counts -> check. Nothing writes the corpus before the user signs off.

Steps run through `prices.weekly.step.run_step`, the `po prices weekly` runner: each one in
its own `systemd-run --user` scope with a MemoryMax, refused unless the 5TB is mounted,
through the disk gate, with STATUS_<step> and events.log under <logs-root>/<run_id>/.
Corpus and ledger live on the 5TB; staging, pending plans, logs and the counts cache
(data/text/cache, outputs/text) are written on a8 (staging/pending under ~/scratch/textsources).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click

from prices.weekly.guards import BACKUP_MOUNT, Refused, free_gb, require_mounted
from prices.weekly.panels import resolve_countries
from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT, Context, Step, run_step

CORPUS_ROOT = BACKUP_MOUNT / "text-corpus"
STATE_DIR = BACKUP_MOUNT / "text-panel" / "state"
# 2026-10-16, user rule: the 5TB is backup only; run outputs default to a8 (floor 10G on /).
STAGING_ROOT = Path.home() / "scratch" / "textsources" / "staging"
# merge writes sign-off plans here; only `signoff` writes the corpus.
PENDING_ROOT = Path.home() / "scratch" / "textsources" / "pending"
LOGS_ROOT = Path.home() / "text_panel" / "logs"
# a8 has no poetry; runner.sh calls `poetry run po`, which this shim maps to ~/venv.
POETRY_SHIM = Path.home() / "text_collect" / "bin"
CHAIN = ["collect", "merge"]
AFTER_SIGNOFF = ["signoff", "counts", "check"]


@dataclass
class PanelContext(Context):
    corpus_root: Path = CORPUS_ROOT
    state_dir: Path = STATE_DIR
    staging_root: Path = STAGING_ROOT
    pending_root: Path = PENDING_ROOT
    parallel: int = 12
    cap: int = 300


def _argv(step: str):
    def argv(c: PanelContext) -> list[str]:
        return [
            "env",
            f"PYTHONPATH={REPO_ROOT / 'src'}",
            f"TEXT_STATE_DIR={c.state_dir}",
            # The panel is the sole writer of what prod excludes; prod's exclude list must not stop its merge.
            "TEXT_COLLECT_EXCLUDE=/dev/null",
            f"PATH={POETRY_SHIM}:{os.environ.get('PATH', '/usr/bin:/bin')}",
            sys.executable,
            "-u",
            "-m",
            "text.panel.steps",
            step,
            "--run-id",
            c.week,
            "--countries",
            ",".join(c.countries or []),
            "--corpus-root",
            str(c.corpus_root),
            "--state-dir",
            str(c.state_dir),
            "--staging-root",
            str(c.staging_root),
            "--pending-root",
            str(c.pending_root),
            "--parallel",
            str(c.parallel),
            "--cap",
            str(c.cap),
            *c.extra,
        ]

    return argv


STEPS: dict[str, Step] = {
    # Once, and again only to re-form it: reads every panel source folder of the corpus.
    "ledger": Step("ledger", "4G", _argv("ledger")),
    # The whole xargs pool shares the scope: P python collects at ~300-500M each.
    "collect": Step("collect", "8G", _argv("collect")),
    # Heavy tier, not in CHAIN: its own timer/run id, e.g. `--run-id <ts>-drain --cap 900 step drain`.
    "drain": Step("drain", "4G", _argv("drain")),
    # Holds one source's url set; the biggest news.csv is ~8.5 GB on disk.
    "merge": Step("merge", "6G", _argv("merge")),
    "signoff": Step("signoff", "6G", _argv("signoff")),
    "counts": Step("counts", "8G", _argv("counts")),
    "check": Step("check", "4G", _argv("check")),
}


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")


def _print_plan(c: PanelContext) -> None:
    from text.panel.steps import panel_sources

    click.echo(f"run {c.week}  logs {c.week_dir}")
    click.echo(f"corpus {c.corpus_root}\nledger {c.state_dir}\nstaging {c.staging_root}")
    total = 0
    for (region, sub, country), srcs in panel_sources(c.countries).items():
        total += len(srcs)
        ledger = "ledger ok" if (c.state_dir / f"{region}.sqlite").exists() else "NO LEDGER"
        click.echo(f"  {region:7s} {country:26s} {len(srcs):4d} sources  {ledger}")
    click.echo(f"{len(c.countries)} countries, {total} enabled text sources")
    try:
        require_mounted(c.backup_mount)
        click.echo(f"mount {c.backup_mount}: ok, {free_gb(c.backup_mount)}G free")
    except Refused as e:
        click.echo(f"mount {c.backup_mount}: steps would refuse ({e})")
    click.echo(f"disk /: {free_gb(Path('/'))}G free")
    for step in STEPS.values():
        run_step(step, c)


def _under_mount(ctx, param, value: Path) -> Path:
    mount = ctx.params.get("backup_mount", BACKUP_MOUNT)
    value = value.expanduser().absolute()
    if not value.is_relative_to(mount):
        raise click.BadParameter(f"{value} is not under {mount}: corpus and ledger live on the 5TB")
    return value


@click.group("panel", invoke_without_command=True)
@click.option(
    "--backup-mount",
    type=click.Path(path_type=Path),
    default=BACKUP_MOUNT,
    show_default=True,
    is_eager=True,
    help="Every step refuses to start unless this is a mount point.",
)
@click.option("--countries", default="text36eap", show_default=True, help="Slugs or a panel name from src/configs/panels/.")
@click.option("--run-id", default=_run_id, show_default="now, UTC (YYYYmmddTHHMMZ)")
@click.option("--corpus-root", type=click.Path(path_type=Path), default=CORPUS_ROOT, show_default=True, callback=_under_mount)
@click.option("--state-dir", type=click.Path(path_type=Path), default=STATE_DIR, show_default=True, callback=_under_mount)
@click.option("--staging-root", type=click.Path(path_type=Path), default=STAGING_ROOT, show_default=True)
@click.option("--pending-root", type=click.Path(path_type=Path), default=PENDING_ROOT, show_default=True)
@click.option("--logs-root", type=click.Path(path_type=Path), default=LOGS_ROOT, show_default=True)
@click.option("--parallel", "-P", type=int, default=12, show_default=True, help="Parallel sources in collect.")
@click.option("--cap", type=int, default=300, show_default=True, help="Seconds per source in collect.")
@click.option("--dry-run", is_flag=True, help="Print the plan; write nothing, run nothing.")
@click.pass_context
def panel(ctx, backup_mount, countries, run_id, corpus_root, state_dir, staging_root, pending_root, logs_root, parallel, cap, dry_run):
    """Text over a panel: steps with STATUS_<step>, MemoryMax, 5TB mount check and disk gate.

    Without a subcommand, prints the plan (implies --dry-run).
    """
    ctx.obj = PanelContext(
        week=run_id,
        logs_root=logs_root,
        countries=resolve_countries(countries),
        dry_run=dry_run or ctx.invoked_subcommand is None,
        backup_mount=backup_mount,
        disk_paths=[Path("/")],
        corpus_root=corpus_root,
        state_dir=state_dir,
        staging_root=staging_root,
        pending_root=pending_root,
        parallel=parallel,
        cap=cap,
    )
    if ctx.invoked_subcommand is None:
        _print_plan(ctx.obj)


@panel.command("step", context_settings={"ignore_unknown_options": True})
@click.argument("name", type=click.Choice(sorted(STEPS)))
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def step_command(c: PanelContext, name: str, extra: tuple[str, ...]):
    """Run one step (ledger, collect, merge, signoff, counts, check)."""
    c.extra = extra
    sys.exit(run_step(STEPS[name], c))


@panel.command("run")
@click.pass_obj
def run_command(c: PanelContext):
    """collect -> merge (a plan) under one run id, then AWAITING_SIGNOFF; the first non-zero exit stops the chain."""
    status = Status(c.week_dir, "run")
    if not c.dry_run:
        status.write("RUNNING", f"{' -> '.join(CHAIN)} over {len(c.countries)} countries")
    for name in CHAIN:
        rc = run_step(STEPS[name], c)
        if rc:
            if not c.dry_run:
                status.write("FAILED", f"stopped at {name} rc={rc}; see STATUS_{name}")
            sys.exit(rc)
    if not c.dry_run:
        status.write("AWAITING_SIGNOFF", f"plan {c.pending_root / c.week}; apply with: po text panel signoff {c.week}")


@panel.command("signoff")
@click.argument("run_id")
@click.pass_obj
def signoff_command(c: PanelContext, run_id: str):
    """Apply the plan <pending-root>/RUN_ID to the corpus and the panel ledger, then counts -> check."""
    c.week = run_id
    status = Status(c.week_dir, "run")
    for name in AFTER_SIGNOFF:
        rc = run_step(STEPS[name], c)
        if rc:
            if not c.dry_run:
                status.write("FAILED", f"stopped at {name} rc={rc}; see STATUS_{name}")
            sys.exit(rc)
    if not c.dry_run:
        status.write("DONE", f"{' -> '.join(CHAIN + AFTER_SIGNOFF)} rc=0")
