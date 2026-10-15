"""`po prices weekly`: the weekly prices run as registered steps."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from prices.weekly.guards import (
    ALERT_USED_PCT,
    BACKUP_MOUNT,
    FLOOR_FREE_GB,
    START_FREE_GB,
    Refused,
    free_gb,
    require_mounted,
    used_pct,
)
from prices.weekly.panels import resolve_countries, sources_by_country
from prices.weekly.status import DEFAULT_LOGS_ROOT, current_week
from prices.weekly.step import REPO_ROOT, Context, run_step
from prices.weekly.steps import STEPS


def _print_plan(c: Context) -> None:
    click.echo(f"week {c.week}  logs {c.week_dir}")
    data = REPO_ROOT / "data"
    click.echo(
        f"tree {REPO_ROOT}  data -> {data.resolve() if data.exists() else '(missing)'}"
    )
    if c.countries:
        counts = sources_by_country(c.countries)
        for country, (n, a) in counts.items():
            click.echo(f"  {country:28s} {n:4d} sources ({a} active)")
        total = sum(n for n, _ in counts.values())
        active = sum(a for _, a in counts.values())
        click.echo(
            f"{len(c.countries)} countries, {total} prices sources ({active} active)"
        )
    else:
        click.echo("countries: all")
    try:
        require_mounted(c.backup_mount)
        click.echo(f"mount {c.backup_mount}: ok")
    except Refused as e:
        click.echo(f"mount {c.backup_mount}: steps would refuse ({e})")
    for p in [c.backup_mount, *c.disk_paths]:
        if p.exists():
            click.echo(f"disk {p}: {free_gb(p)}G free, {used_pct(p)}% used")
    click.echo(
        f"gate: start >= {START_FREE_GB}G free, stop < {FLOOR_FREE_GB}G, alert >= {ALERT_USED_PCT}% used"
    )
    for step in STEPS.values():
        run_step(step, c)


@click.group("weekly", invoke_without_command=True)
@click.option("--week", default=current_week, show_default="current ISO week, UTC")
@click.option(
    "--countries",
    default=None,
    help="Comma-separated country slugs, or a panel name from src/configs/panels/ (e.g. panel36).",
)
@click.option(
    "--logs-root",
    type=click.Path(path_type=Path),
    default=DEFAULT_LOGS_ROOT,
    show_default=True,
)
@click.option(
    "--backup-mount",
    type=click.Path(path_type=Path),
    default=BACKUP_MOUNT,
    show_default=True,
    help="Every step refuses to start unless this is a mount point.",
)
@click.option(
    "--dry-run", is_flag=True, help="Print the plan; write nothing, run nothing."
)
@click.pass_context
def weekly(ctx, week, countries, logs_root, backup_mount, dry_run):
    """Weekly prices run: steps with STATUS_<step>, MemoryMax, 5TB mount check and disk gate.

    Without a subcommand, prints the plan for --countries (implies --dry-run).
    """
    ctx.obj = Context(
        week=week,
        logs_root=logs_root,
        countries=resolve_countries(countries),
        dry_run=dry_run or ctx.invoked_subcommand is None,
        backup_mount=backup_mount,
        disk_paths=[Path("/")],
    )
    if ctx.invoked_subcommand is None:
        _print_plan(ctx.obj)


@weekly.command("step")
@click.argument("name", type=click.Choice(sorted(STEPS)))
@click.pass_obj
def step_command(c: Context, name: str):
    """Run one registered step."""
    sys.exit(run_step(STEPS[name], c))
