"""`po text panel`: the text chain over a country panel, collect -> merge (a plan) -> AWAITING_SIGNOFF,
then `signoff <run_id>` -> counts -> check -> aggregate -> publish. Nothing writes the corpus
before the user signs off; a red check stops aggregate and publish (`step <name>` runs one alone).

Steps run through `prices.weekly.step.run_step`, the `po prices weekly` runner: each one in
its own `systemd-run --user` scope with a MemoryMax, refused unless the 5TB is mounted,
through the disk gate, with STATUS_<step> and events.log under <logs-root>/<run_id>/.
Corpus and sign-off plans (pending, the backup of every merged row) live on the 5TB; ledger,
staging, logs and the dashboards of publish on a8's disk. The counts cache and outputs go where
the worktree's data/text/cache and outputs/text/<region> links point. The disk gate measures /
and the 5TB: start at 15G free, and the panel stops a step below 10G on / (prices keeps 5G).
A staging run is pruned by signoff once its plan is applied (text.panel.signoff.prune_staging);
publish keeps the newest PUBLISH_KEEP runs.
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
# The panel ledger lives on a8's disk (the 5TB is backup only). It is never created
# here: a missing dir would mean an empty ledger and a re-seeded collect.
STATE_DIR = Path.home() / "text_panel" / "state"
# Collect output on a8's disk; signoff prunes a run once its rows are in the applied plan.
STAGING_ROOT = Path.home() / "text_panel" / "staging"
# merge writes sign-off plans here; only `signoff` writes the corpus.
PENDING_ROOT = BACKUP_MOUNT / "text-panel" / "pending"
# Internal dashboards (TX-32), one folder per run id, on a8's own disk: the 5TB is backup only.
# Nothing is published outside; they reach the Mac by rsync.
PUBLISH_ROOT = Path.home() / "text_panel" / "publish"
# One job over 8G at a time on a8.
HEAVY_LOCK = Path.home() / "scratch" / "heavy.lock"
LOGS_ROOT = Path.home() / "text_panel" / "logs"
# a8 has no poetry; runner.sh calls `poetry run po`, which this shim maps to ~/venv.
POETRY_SHIM = Path.home() / "text_collect" / "bin"
CHAIN = ["collect", "merge"]
AFTER_SIGNOFF = ["signoff", "counts", "check", "aggregate", "publish"]


@dataclass
class PanelContext(Context):
    corpus_root: Path = CORPUS_ROOT
    state_dir: Path = STATE_DIR
    staging_root: Path = STAGING_ROOT
    pending_root: Path = PENDING_ROOT
    publish_root: Path = PUBLISH_ROOT
    parallel: int = 12
    cap: int = 300


def _argv(step: str, lock: bool = False):
    def argv(c: PanelContext) -> list[str]:
        return [
            *(["flock", str(HEAVY_LOCK)] if lock else []),
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
            "--publish-root",
            str(c.publish_root),
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
    # Holds one source's url set; the biggest news.csv is ~8.5 GB on disk.
    "merge": Step("merge", "6G", _argv("merge")),
    "signoff": Step("signoff", "6G", _argv("signoff")),
    "counts": Step("counts", "8G", _argv("counts")),
    "check": Step("check", "4G", _argv("check")),
    # Re-reads every news.csv of the region through the cache gate, like `po text build --region`.
    "aggregate": Step("aggregate", "12G", _argv("aggregate", lock=True)),
    # Holds dashboard_data.json of every unit and one region's HTML (up to ~80 MB) as strings.
    "publish": Step("publish", "6G", _argv("publish")),
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
        raise click.BadParameter(f"{value} is not under {mount}: corpus and plans live on the 5TB")
    return value


def _existing_dir(ctx, param, value: Path) -> Path:
    value = value.expanduser().absolute()
    if not value.is_dir():
        raise click.BadParameter(f"{value} does not exist: the panel ledger is not created empty "
                                 "(migrate it, or mkdir it on purpose before `step ledger`)")
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
@click.option("--state-dir", type=click.Path(path_type=Path), default=STATE_DIR, show_default=True, callback=_existing_dir)
@click.option("--staging-root", type=click.Path(path_type=Path), default=STAGING_ROOT, show_default=True)
@click.option("--pending-root", type=click.Path(path_type=Path), default=PENDING_ROOT, show_default=True, callback=_under_mount)
@click.option("--publish-root", type=click.Path(path_type=Path), default=PUBLISH_ROOT, show_default=True)
@click.option("--logs-root", type=click.Path(path_type=Path), default=LOGS_ROOT, show_default=True)
@click.option("--parallel", "-P", type=int, default=12, show_default=True, help="Parallel sources in collect.")
@click.option("--cap", type=int, default=300, show_default=True, help="Seconds per source in collect.")
@click.option("--dry-run", is_flag=True, help="Print the plan; write nothing, run nothing.")
@click.pass_context
def panel(ctx, backup_mount, countries, run_id, corpus_root, state_dir, staging_root, pending_root, publish_root, logs_root,
          parallel, cap, dry_run):
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
        floor_free_gb=10,
        corpus_root=corpus_root,
        state_dir=state_dir,
        staging_root=staging_root,
        pending_root=pending_root,
        publish_root=publish_root,
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
    """Run one step (ledger, collect, merge, signoff, counts, check, aggregate, publish)."""
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
    """Apply the plan <pending-root>/RUN_ID to the corpus and the panel ledger, then counts -> check
    -> aggregate -> publish."""
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
