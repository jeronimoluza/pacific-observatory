"""Unified CLI entry point: `po`

Usage:
    po                           Show home screen
    po status                    Compute pipeline health
    po list-regions              Show region/subregion/country topology
    po text collect [options]    Scrape articles
    po text build   [options]    Run EPU calculation
    po text publish [options]    Generate dashboards
    po text status  [options]    Per-source health table
    po fuel ...                  [not migrated]
    po prices ...                [not migrated]
    po init --region <name>      Scaffold directories
"""

import click

from core.config import make_slug_validator


# ── Main group ─────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.version_option(package_name="pacific-observatory")
@click.pass_context
def po(ctx):
    """Pacific Observatory data pipelines."""
    if ctx.invoked_subcommand is None:
        _render_home()


def _render_home():
    """Print the po home screen with optional cached snapshot."""
    import importlib.metadata

    try:
        version = importlib.metadata.version("pacific-observatory")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    from text.status import read_status_cache

    cache = read_status_cache()

    lines = [
        "",
        f"  Pacific Observatory (po) v{version}",
        "",
        "  Pipelines:",
        "    po text      Newspaper scraping and EPU analysis",
        "    po fuel      [not migrated]",
        "    po prices    [not migrated]",
        "",
    ]

    if cache:
        computed_at = cache.get("computed_at", "unknown")
        lines.append(
            f"  Snapshot (computed {computed_at} — run 'po status' to refresh):"
        )

        text = cache.get("text", {})
        collect = text.get("collect", {})
        scraped = collect.get("sources_scraped", 0)
        total = collect.get("sources_total", 0)
        articles = collect.get("articles_total", 0)
        art_str = f"{articles / 1000:.0f}k" if articles >= 1000 else str(articles)
        last = collect.get("last_scraped_at", "—") or "—"

        lines.append(
            f"    text    {scraped}/{total} sources scraped · "
            f"{art_str} articles · last scraped {last}"
        )
        lines.append("    fuel    [not migrated]")
        lines.append("    prices  [not migrated]")
    else:
        lines.append("  Snapshot:")
        lines.append("    (no data — run 'po status')")

    lines.extend(
        [
            "",
            "  Common Commands:",
            "    po text collect --dry-run      Preview scraping plan",
            "    po text collect --list         List configured sources",
            "    po text collect --country <x>  Scrape a single country",
            "    po text build                  Run EPU index calculation",
            "    po text publish                Generate dashboards",
            "    po text status                 Source health and article stats",
            "    po list-regions                Show region/subregion/country topology",
            "    po status                      Compute and cache pipeline health",
            "",
            "  Filters:  -r/--region  -S/--subregion  -c/--country  -s/--source",
            "",
        ]
    )
    click.echo("\n".join(lines))


# ── Pipeline groups ────────────────────────────────────────────────


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

_region_opt = click.option(
    "--region",
    "-r",
    default=None,
    callback=make_slug_validator("region"),
    help="Filter by region slug",
)
_subregion_opt = click.option(
    "--subregion",
    "-S",
    default=None,
    callback=make_slug_validator("subregion"),
    help="Filter by subregion slug",
)
_country_opt = click.option(
    "--country",
    "-c",
    default=None,
    callback=make_slug_validator("country"),
    help="Filter by country slug",
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
@click.option("--rebuild", is_flag=True, help="Delete and re-fetch from fallback date")
@click.option("--force", is_flag=True, help="Run disabled sources")
def fuel_collect(region, subregion, country, source, yes, dry_run, rebuild, force):
    """Fetch new fuel price observations from configured sources."""
    import logging

    from fuel.collect import run_collection
    from fuel.config import build_fuel_registry

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    try:
        registry = build_fuel_registry(
            region=region,
            subregion=subregion,
            country=country,
            source_key=source,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if not registry:
        raise click.ClickException(
            "No fuel sources found. Check --region/--subregion/--country/--source filters."
        )

    if not yes and not dry_run:
        sources_list = ", ".join(sorted(registry))
        click.echo(f"Sources to collect: {sources_list}")
        if not click.confirm("Proceed?"):
            raise SystemExit(0)

    run_collection(
        registry=registry,
        source_key=source,
        force=force,
        rebuild=rebuild,
        dry_run=dry_run,
    )


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
@click.option(
    "--list", "list_sources", is_flag=True, help="List configured sources (YAML only)"
)
@click.option("--max-pages", type=int, default=None, help="Limit pages per newspaper")
@click.option(
    "--max-articles", type=int, default=None, help="Limit articles per newspaper"
)
@click.option("--rebuild", is_flag=True, help="Full re-scrape (bypass URL dedup)")
def text_collect(
    region,
    subregion,
    country,
    source,
    yes,
    dry_run,
    list_sources,
    max_pages,
    max_articles,
    rebuild,
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
        list_sources=list_sources,
    )


@text.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@_yes_opt
@click.option(
    "--cutoff-start-date",
    type=str,
    default=None,
    help="Inclusive baseline start date for EPU standardization (YYYY-MM-DD)",
)
@click.option(
    "--cutoff-end-date",
    type=str,
    default=None,
    help="Inclusive baseline end date for EPU standardization (YYYY-MM-DD)",
)
@click.option(
    "--rebuild",
    is_flag=True,
    default=False,
    help="Force recalculation of params.json and cache.",
)
def text_build(
    region, subregion, country, yes, cutoff_start_date, cutoff_end_date, rebuild
):
    """Run EPU index calculation and analysis."""
    from text.process import run_build

    run_build(
        region=region,
        subregion=subregion,
        country=country,
        yes=yes,
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
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


@text.command("status")
@_region_opt
@_subregion_opt
@_country_opt
@click.option("--all", "show_all", is_flag=True, help="Include unscraped sources")
def text_status(region, subregion, country, show_all):
    """Show per-source health table with article counts and freshness."""
    from text.collect import display_status

    display_status(
        region=region, subregion=subregion, country=country, show_all=show_all
    )


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


@po.command("list-regions")
def list_regions():
    """Show region/subregion/country topology from regions.yaml."""
    from core.config import format_regions_table

    click.echo()
    click.echo(format_regions_table())
    click.echo()


@po.command()
def status():
    """Compute and display pipeline health across all pipelines."""
    from datetime import datetime, timezone

    from text.status import compute_text_status, write_status_cache

    click.echo("  Computing pipeline status...")
    text_data = compute_text_status()

    cache = {
        "computed_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "text": text_data,
        "fuel": {"migrated": False},
        "prices": {"migrated": False},
    }
    write_status_cache(cache)

    collect = text_data["collect"]
    build = text_data["build"]
    publish = text_data["publish"]

    articles = collect["articles_total"]
    art_str = f"{articles:,}" if articles >= 1000 else str(articles)

    click.echo()
    click.echo("  Text Pipeline:")
    click.echo(
        f"    collect   {collect['sources_scraped']}/{collect['sources_total']} "
        f"sources scraped · {art_str} articles · {collect['countries_total']} countries · "
        f"{collect['date_earliest'] or '—'} → {collect['date_latest'] or '—'} · "
        f"last scraped {collect['last_scraped_at'] or '—'}"
    )
    click.echo(
        f"    build     {build['epu_outputs']} outputs · "
        f"last built {build['last_built_at'] or '—'}"
    )

    if publish["dashboard_data"] or publish["dashboard_html"]:
        files = []
        if publish["dashboard_data"]:
            files.append("dashboard_data.json")
        if publish["dashboard_html"]:
            files.append("small_dashboard_integrated.html")
        click.echo(
            f"    publish   {', '.join(files)} · "
            f"last published {publish['last_published_at'] or '—'}"
        )
    else:
        click.echo("    publish   no dashboard output found")

    click.echo()
    click.echo("  Fuel Pipeline:    [not migrated]")
    click.echo("  Prices Pipeline:  [not migrated]")
    click.echo()
    click.echo("  Cache written to data/.po_cache.json")
    click.echo()


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
