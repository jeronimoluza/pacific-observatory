"""Unified CLI entry point for the Pacific Observatory.

Usage:
    python run.py                Show home screen in this repo
    python run.py text collect   Scrape articles
    poetry run po --help         Use the installed alias
"""

import click

from cli_display import command_prefix, text_help_examples, top_level_help_examples
from core.config import make_slug_validator


# ── Main group ─────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.version_option(package_name="pacific-observatory")
@click.pass_context
def po(ctx):
    """Pacific Observatory data pipelines for local repo use and the installed `po` alias."""
    if ctx.invoked_subcommand is None:
        _render_home()


def _render_home():
    """Print the CLI home screen with optional cached snapshot."""
    import importlib.metadata

    try:
        version = importlib.metadata.version("pacific-observatory")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    from text.status import read_status_cache

    cache = read_status_cache()

    lines = [
        "",
        f"  Pacific Observatory CLI v{version}",
        "",
        f"  Repo-local: {command_prefix()}",
        "  Installed alias: po",
        "",
        "  Pipelines:",
        f"    {command_prefix()} text      Newspaper scraping and EPU analysis",
        f"    {command_prefix()} fuel      [not migrated]",
        f"    {command_prefix()} prices    [not migrated]",
        "",
    ]

    if cache:
        computed_at = cache.get("computed_at", "unknown")
        lines.append(
            f"  Snapshot (computed {computed_at} — run '{command_prefix()} status' to refresh):"
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
        lines.append(f"    (no data — run '{command_prefix()} status')")

    lines.extend(
        [
            "",
            "  Start Here:",
            f"    {command_prefix()} list-regions                             Show region/subregion/country topology",
            f"    {command_prefix()} text collect --list --country <slug>     List configured newspaper keys",
            f"    {command_prefix()} text collect --country <slug> --dry-run  Preview a scrape safely",
            "",
            "  Typical Workflow:",
            f"    {command_prefix()} text collect --country <slug>            Scrape a single country",
            f"    {command_prefix()} text build --country <slug>              Compute EPU outputs",
            f"    {command_prefix()} text publish --country <slug>            Generate dashboards",
        ]
        + [
            "",
            "  Filters:  -r/--region  -S/--subregion  -c/--country  -s/--source (newspaper key)",
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
_text_source_opt = click.option(
    "--source", "-s", default=None, help="Run a single configured newspaper key"
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
@_text_source_opt
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
@click.option(
    "--resume",
    is_flag=True,
    help="Scrape only pending URLs from urls.csv (no discovery)",
)
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
    resume,
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
        resume=resume,
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
    po.epilog = top_level_help_examples()
    text.epilog = text_help_examples()
    po()


if __name__ == "__main__":
    main()
