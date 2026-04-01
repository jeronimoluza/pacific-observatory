"""Unified CLI entry point: `po`

Usage:
    po fuel collect [--region R] [--subregion S] [--country C] [--source S] [-y] [--dry-run]
    po fuel build   [--region R] [--subregion S] [--country C] [-y]
    po fuel publish [--region R] [--subregion S] [-y]
    po text collect [--region R] [--subregion S] [--country C] [--source S] [-y] [--dry-run]
    po text build   [--region R] [--subregion S] [--country C] [-y]
    po text publish [--region R] [--subregion S] [-y]
    po prices collect [--region R] [--subregion S] [--country C] [-y] [--dry-run]
    po prices build   [--region R] [--subregion S] [--country C] [-y]
    po prices publish [--region R] [--subregion S] [-y]
    po status
    po init --region <name>
"""

import click


@click.group()
@click.version_option()
def po():
    """Pacific Observatory data pipelines."""


# ── Pipeline groups (stubs — replaced during migration) ─────────────


@po.group()
def fuel():
    """Fuel price monitoring pipeline."""


@po.group()
def text():
    """Newspaper scraping and EPU analysis pipeline."""


@po.group()
def prices():
    """Supermarket price scraping, COICOP classification, and CPI pipeline."""


# ── Shared option decorators ────────────────────────────────────────

_region_opt = click.option("--region", "-r", default=None, help="Filter by region slug")
_subregion_opt = click.option(
    "--subregion", default=None, help="Filter by subregion slug"
)
_country_opt = click.option(
    "--country", "-c", default=None, help="Filter by country slug"
)
_source_opt = click.option(
    "--source", "-s", default=None, help="Run a single source key"
)
_yes_opt = click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
_dry_run_opt = click.option(
    "--dry-run", is_flag=True, help="Show plan without executing"
)


# ── Fuel subcommands ────────────────────────────────────────────────


@fuel.command("collect")
@_region_opt
@_subregion_opt
@_country_opt
@_source_opt
@_yes_opt
@_dry_run_opt
def fuel_collect(region, subregion, country, source, yes, dry_run):
    """Fetch new fuel price observations from configured sources."""
    click.echo("fuel collect: not yet migrated")


@fuel.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@_yes_opt
def fuel_build(region, subregion, country, yes):
    """Process raw observations into enriched dataset."""
    click.echo("fuel build: not yet migrated")


@fuel.command("publish")
@_region_opt
@_subregion_opt
@_yes_opt
def fuel_publish(region, subregion, yes):
    """Generate dashboards and HTML outputs."""
    click.echo("fuel publish: not yet migrated")


# ── Text subcommands ────────────────────────────────────────────────


@text.command("collect")
@_region_opt
@_subregion_opt
@_country_opt
@_source_opt
@_yes_opt
@_dry_run_opt
@click.option("--max-pages", type=int, default=None, help="Limit pages per newspaper")
@click.option(
    "--max-articles", type=int, default=None, help="Limit articles per newspaper"
)
@click.option("--rebuild", is_flag=True, help="Full re-scrape (bypass URL dedup)")
def text_collect(
    region, subregion, country, source, yes, dry_run, max_pages, max_articles, rebuild
):
    """Scrape new articles from configured newspapers."""
    from text.collect import run_collect

    run_collect(
        region=region,
        subregion=subregion,
        country=country,
        source=source,
        max_pages=max_pages,
        max_articles=max_articles,
        dry_run=dry_run,
        yes=yes,
        rebuild=rebuild,
    )


@text.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@_yes_opt
@click.option(
    "--cutoff",
    type=str,
    default=None,
    help="Cutoff date for EPU standardization (YYYY-MM-DD)",
)
@click.option(
    "--rebuild",
    is_flag=True,
    default=False,
    help="Force recalculation of params.json and cache.",
)
def text_build(region, subregion, country, yes, cutoff, rebuild):
    """Run EPU index calculation and analysis."""
    from text.process import run_build

    run_build(
        region=region,
        subregion=subregion,
        country=country,
        yes=yes,
        cutoff=cutoff,
        rebuild=rebuild,
    )


@text.command("publish")
@_region_opt
@_subregion_opt
@_country_opt
@_yes_opt
def text_publish(region, subregion, country, yes):
    """Generate EPU dashboards and charts."""
    from text.publish import run_publish

    run_publish(region=region, subregion=subregion, country=country, yes=yes)


# ── Prices subcommands ──────────────────────────────────────────────


@prices.command("collect")
@_region_opt
@_subregion_opt
@_country_opt
@_source_opt
@_yes_opt
@_dry_run_opt
def prices_collect(region, subregion, country, source, yes, dry_run):
    """Scrape supermarket prices from configured retailers."""
    click.echo("prices collect: not yet migrated")


@prices.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@_yes_opt
def prices_build(region, subregion, country, yes):
    """Classify products (COICOP) and construct CPI indices."""
    click.echo("prices build: not yet migrated")


@prices.command("publish")
@_region_opt
@_subregion_opt
@_yes_opt
def prices_publish(region, subregion, yes):
    """Generate CPI dashboards."""
    click.echo("prices publish: not yet migrated")


# ── Cross-cutting commands ──────────────────────────────────────────


@po.command()
def status():
    """Show source health across all pipelines."""
    click.echo("status: not yet migrated")


@po.command()
@click.option("--region", required=True, help="Region slug to scaffold")
def init(region):
    """Scaffold directories for a new region."""
    click.echo(f"init --region {region}: not yet implemented")


# ── Entry point ─────────────────────────────────────────────────────


def main():
    po()


if __name__ == "__main__":
    main()
