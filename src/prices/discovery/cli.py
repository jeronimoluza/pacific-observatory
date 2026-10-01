"""`po prices discovery ...` -- the candidates store's command line."""

from __future__ import annotations

from pathlib import Path

import click

from prices.discovery.db import DEFAULT_DB, connect


@click.group("discovery")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_DB,
    show_default=True,
    help="Discovery SQLite file.",
)
@click.pass_context
def discovery_group(ctx: click.Context, db_path: Path) -> None:
    """Find price sources with daily search budgets; track candidates to onboarding."""
    ctx.obj = {"db_path": db_path}


@discovery_group.command("seed")
@click.pass_context
def seed_command(ctx: click.Context) -> None:
    """Load countries, onboarded config domains, engines and skill inventories."""
    from prices.discovery.seed import seed_countries_and_configs, seed_inventories

    con = connect(ctx.obj["db_path"])
    with con:
        cfg = seed_countries_and_configs(con)
        inv = seed_inventories(con)
    click.echo(
        f"country dirs: {cfg['country_dirs']}  countries: {cfg['countries']}  configs read: {cfg['configs']}"
    )
    click.echo(f"onboarded (country, domain) pairs: {cfg['onboarded_pairs']}")
    click.echo(
        f"countries with no YAML ({len(cfg['empty_countries'])}): {', '.join(cfg['empty_countries'])}"
    )
    click.echo(f"inventory rows inserted: {inv['inventory_inserted']}  {inv['by_status']}")
    if inv["unmatched"]:
        click.echo(f"inventory files with no matching country dir: {', '.join(inv['unmatched'])}")


@discovery_group.command("status")
@click.option("--country", default=None, help="List one country's candidates.")
@click.pass_context
def status_command(ctx: click.Context, country: str | None) -> None:
    """Candidate counts by status, engine budgets, or one country's rows."""
    con = connect(ctx.obj["db_path"])
    if country:
        for r in con.execute(
            "SELECT status, domain, source_config, reason FROM candidates WHERE country = ? ORDER BY status, domain",
            (country,),
        ):
            click.echo(
                f"{r['status']:<14} {r['domain']:<40} {r['source_config'] or r['reason'] or ''}"
            )
        return
    n_countries = con.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    click.echo(f"countries: {n_countries}")
    for r in con.execute(
        "SELECT status, COUNT(*) n FROM candidates GROUP BY status ORDER BY n DESC"
    ):
        click.echo(f"  {r['status']:<14} {r['n']}")
    click.echo("engines:")
    for r in con.execute(
        "SELECT engine, daily_cap, parked_until FROM engines ORDER BY daily_cap DESC, engine"
    ):
        parked = f"  parked until {r['parked_until']}" if r["parked_until"] else ""
        click.echo(f"  {r['engine']:<12} cap {r['daily_cap']}{parked}")
