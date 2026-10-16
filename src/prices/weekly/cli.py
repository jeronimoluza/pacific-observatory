"""`po prices weekly`: the weekly prices run as registered steps."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from prices.weekly.chain import ORDER, run_chain
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


@weekly.command("step", context_settings={"ignore_unknown_options": True})
@click.argument("name", type=click.Choice(sorted(STEPS)))
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def step_command(c: Context, name: str, extra: tuple[str, ...]):
    """Run one registered step; EXTRA goes to its runner (e.g. stage_b --out DIR --as-of DATE)."""
    c.extra = extra
    sys.exit(run_step(STEPS[name], c))


@weekly.command("diff")
@click.argument("a", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("b", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--countries",
    "only",
    default=None,
    help="Slugs or a panel name; default the group's --countries, else every country in A or B.",
)
@click.pass_obj
def diff_command(c: Context, a: Path, b: Path, only: str | None):
    """Compare two per-country output trees (e.g. two Stage B roots); exit 1 on any DIFF."""
    from prices.weekly.diff import diff_trees

    sys.exit(diff_trees(a, b, resolve_countries(only) or c.countries))


@weekly.command("run")
@click.option("--from", "first", type=click.Choice(ORDER), default=ORDER[0], show_default=True)
@click.option("--to", "last", type=click.Choice(ORDER), default=ORDER[-1], show_default=True)
@click.option("--week", default=None, help="Overrides the group's --week.")
@click.option("--countries", default=None, help="Overrides the group's --countries.")
@click.option("--dry-run", is_flag=True, help="List the steps, their units and gates; run nothing.")
@click.option(
    "--trust-upstream",
    is_flag=True,
    help="Skip the gate on the step before --from (its STATUS need not be DONE); written to STATUS_run.",
)
@click.pass_obj
def run_command(c: Context, first, last, week, countries, dry_run, trust_upstream):
    """Run the steps --from..--to in order, each gated on the one before it ending DONE."""
    if week:
        c.week = week
    if countries:
        c.countries = resolve_countries(countries)
    c.dry_run = c.dry_run or dry_run
    sys.exit(run_chain(c, first, last, trust_upstream))
