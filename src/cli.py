"""Unified CLI entry point for the Pacific Observatory.

Usage:
    python run.py                Show home screen in this repo
    python run.py text collect   Scrape articles
    poetry run po --help         Use the installed alias
"""

import click

from cli_display import render_home, text_help_examples, top_level_help_examples
from core.config import make_slug_validator


# ── Main group ─────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.version_option(package_name="pacific-observatory")
@click.pass_context
def po(ctx):
    """Pacific Observatory data pipelines for local repo use and the installed `po` alias."""
    if ctx.invoked_subcommand is None:
        render_home()


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
_dry_run_opt = click.option(
    "--dry-run", is_flag=True, help="Show plan without executing"
)


_fuel_region_opt = click.option(
    "--region",
    "-r",
    default=None,
    callback=make_slug_validator("region", extra_valid={"global"}),
    help="Filter by region slug (use 'global' for commodity benchmarks)",
)


# ── Fuel subcommands ────────────────────────────────────────────────


@fuel.command("collect")
@_fuel_region_opt
@_subregion_opt
@_country_opt
@_source_opt
@_dry_run_opt
@click.option("--rebuild", is_flag=True, help="Delete and re-fetch from fallback date")
@click.option("--force", is_flag=True, help="Run disabled sources")
def fuel_collect(region, subregion, country, source, dry_run, rebuild, force):
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
            include_global=bool(region and region != "global"),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if not registry:
        raise click.ClickException(
            "No fuel sources found. Check --region/--subregion/--country/--source filters."
        )

    if not dry_run:
        sources_list = ", ".join(sorted(registry))
        click.echo(f"Sources to collect: {sources_list}")

    run_collection(
        registry=registry,
        source_key=source,
        force=force,
        rebuild=rebuild,
        dry_run=dry_run,
        refresh_fx=bool(region and region != "global"),
    )


@fuel.command("build")
@_region_opt
@_subregion_opt
@_country_opt
def fuel_build(region, subregion, country):
    """Process raw observations into enriched dataset."""
    import logging

    from fuel.process import run_build

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    try:
        run_build(region=region, subregion=subregion, country=country)
    except ValueError as exc:
        raise click.ClickException(str(exc))


@fuel.command("publish")
@_region_opt
@_subregion_opt
def fuel_publish(region, subregion):
    """Generate fuel policy dashboards."""
    import logging

    from fuel.publish import run_publish

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    try:
        run_publish(region=region, subregion=subregion)
    except ValueError as exc:
        raise click.ClickException(str(exc))


# ── Text subcommands ────────────────────────────────────────────────


@text.command("collect")
@_region_opt
@_subregion_opt
@_country_opt
@_text_source_opt
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
@click.option(
    "--retry-failed",
    "retry_failed",
    is_flag=True,
    help=(
        "Re-attempt URLs in failed_urls_seen.csv (the cumulative ledger of "
        "URLs that have failed before). Without this flag those URLs are "
        "skipped. Use after fixing a parser to recover previously-failed "
        "articles. Cannot be combined with --rebuild."
    ),
)
def text_collect(
    region,
    subregion,
    country,
    source,
    dry_run,
    list_sources,
    max_pages,
    max_articles,
    rebuild,
    resume,
    retry_failed,
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
        rebuild=rebuild,
        resume=resume,
        retry_failed=retry_failed,
        list_sources=list_sources,
    )


@text.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@click.option(
    "--cutoff-start-date",
    type=str,
    default=None,
    help="Inclusive baseline start date for EPU standardization (YYYY-MM-DD)",
)
@click.option(
    "--cutoff-end-date",
    type=str,
    default="2020-12-31",
    show_default=True,
    help="Inclusive baseline end date for EPU standardization (YYYY-MM-DD)",
)
@click.option(
    "--rebuild",
    is_flag=True,
    default=False,
    help="Force recalculation of params.json and cache.",
)
@click.option(
    "--max-parallel-sources",
    type=int,
    default=1,
    show_default=True,
    help="Bound on concurrent per-source annotation. Increase for speed; keep at 1 for memory safety.",
)
def text_build(
    region,
    subregion,
    country,
    cutoff_start_date,
    cutoff_end_date,
    rebuild,
    max_parallel_sources,
):
    """Run EPU index calculation and analysis."""
    from text.process import run_build

    if max_parallel_sources < 1:
        raise click.BadParameter("--max-parallel-sources must be >= 1")

    run_build(
        region=region,
        subregion=subregion,
        country=country,
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
        rebuild=rebuild,
        max_parallel_sources=max_parallel_sources,
    )


@text.command("publish")
@_region_opt
@_subregion_opt
@_country_opt
@click.option(
    "--tracker",
    default="fuel",
    type=click.Choice(["fuel", "food"]),
    help="Policy-tracker variant for the policy tab. Default: fuel.",
)
@click.option(
    "--skip-database-status",
    is_flag=True,
    help="Skip the global raw-data rescan; only build dashboards",
)
def text_publish(region, subregion, country, tracker, skip_database_status):
    """Generate EPU dashboards and charts."""
    from text.publish import run_publish

    run_publish(
        region=region,
        subregion=subregion,
        country=country,
        tracker=tracker,
        skip_database_status=skip_database_status,
    )


@text.command("build-policy-addons")
@click.option(
    "--region",
    "-r",
    default=None,
    callback=make_slug_validator("region"),
    help="Region slug; omit to build all six.",
)
@click.option(
    "--chart-title",
    default=None,
    help="Optional chart title embedded in the HTML. Defaults to today's date.",
)
@click.option(
    "--tracker",
    default="fuel",
    type=click.Choice(["fuel", "food"]),
    help="Policy-tracker variant to build. Default: fuel.",
)
def text_build_policy_addons(region, chart_title, tracker):
    """Build policy addon HTMLs from data/text/policy_tracker/<region>.xlsx."""
    from text.plotting.policy_dashboards import build_addons

    build_addons(region=region, chart_title=chart_title, tracker=tracker)


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


@text.command("database-status")
@_region_opt
@click.option(
    "--merge-only",
    is_flag=True,
    help="Skip scanning; rebuild sources.xlsx from existing per-region exports",
)
def text_database_status(region, merge_only):
    """Export verified per-source article counts + date ranges to outputs/text/database_status/.

    With --region, scans just that region and writes sources_<region>.*, then
    refreshes the combined sources.xlsx (one sheet per region) from every
    per-region export on disk. Regions whose raw data is currently archived
    keep their sheet — they are merged from their own export, not re-scanned.
    """
    from text.status import (
        compute_database_status,
        merge_region_exports,
        write_database_status,
    )

    if not merge_only:
        click.echo(
            f"  Scanning data/text/{region + '/' if region else ''} for news.csv files..."
        )
        data = compute_database_status(region_filter=region)
        paths = write_database_status(data, region=region)
        t = data["totals"]
        click.echo(
            f"\n  {t['sources']} sources · {t['articles_total']:,} articles · "
            f"{t['countries']} countries\n"
            f"  Coverage: {t['earliest_date'] or '—'} → {t['latest_date'] or '—'}\n"
            f"  Wrote {paths['csv']}\n  Wrote {paths['json']}\n  Wrote {paths['xlsx']}\n"
        )

    if not region and not merge_only:
        return  # a full unscoped scan already wrote the global export

    merged = merge_region_exports()
    click.echo("  Combined workbook (one sheet per region):")
    for row in merged["regions"]:
        click.echo(
            f"    {row['region'].upper():<8} {row['sources']:>4} sources · "
            f"{(row['articles_total'] or 0):>10,} articles · scanned {row['scanned_at']}"
        )
    m = merged["totals"]
    click.echo(
        f"\n  {m['regions']} regions · {m['sources']} sources · "
        f"{m['articles_total']:,} articles · {m['countries']} countries\n"
        f"  Wrote {merged['xlsx']}\n"
    )


# ── Two-tier storage commands (archive / restore / storage-status) ──
# Registered from cli_text_storage.py to keep cli.py under the 500-line cap.

from cli_text_storage import register as _register_text_storage  # noqa: E402

_register_text_storage(
    text,
    {
        "region": _region_opt,
        "subregion": _subregion_opt,
        "country": _country_opt,
        "source": _text_source_opt,
    },
)


# ── Prices subcommands ──────────────────────────────────────────────


from prices.collect import collect as _prices_collect  # noqa: E402
from prices.backfill_cli import backfill_command as _prices_backfill  # noqa: E402
from prices.cc_cli import common_crawl_command as _prices_common_crawl  # noqa: E402
from prices.cc_table_cli import cc_table_group as _prices_cc_table  # noqa: E402
from prices.enrich.cli import process_command as _prices_process  # noqa: E402
from prices.enrich.eval.cli import eval_command as _prices_eval  # noqa: E402
from prices.enrich.match_record_view import (  # noqa: E402
    match_record_command as _prices_match_record,
)
from prices.enrich.census import census_command as _prices_census  # noqa: E402
from prices.enrich.coverage import coverage_command as _prices_coverage  # noqa: E402
from prices.enrich.classifier.cli import (  # noqa: E402
    train_classifier_command as _prices_train_classifier,
)
from prices.enrich.label_cli import label_group as _prices_label  # noqa: E402
from prices.enrich.gold_audit.cli import (  # noqa: E402
    gold_audit_group as _prices_gold_audit,
)

prices.add_command(_prices_collect, name="collect")
prices.add_command(_prices_backfill, name="backfill")
prices.add_command(_prices_common_crawl, name="common-crawl")
prices.add_command(_prices_cc_table, name="cc-table")
prices.add_command(_prices_process, name="process")
prices.add_command(_prices_eval, name="eval")
prices.add_command(_prices_match_record, name="match-record")
prices.add_command(_prices_census, name="census")
prices.add_command(_prices_coverage, name="coverage")
prices.add_command(_prices_train_classifier, name="train-classifier")
prices.add_command(_prices_label, name="label")
prices.add_command(_prices_gold_audit, name="gold-audit")


@prices.command("build")
@_region_opt
@_subregion_opt
@_country_opt
def prices_build(region, subregion, country):
    """Construct CPI indices from the enriched prices dataset.

    PoC scope: writes the EAP × F&B basket parquet at
    data/prices/build/eap_fnb_observations.parquet. Region/subregion/
    country flags are accepted but ignored until the basket widens
    beyond the EAP PoC.
    """
    from prices.build.aggregate import run as _build_run

    _build_run()


@prices.command("publish")
@_region_opt
@_subregion_opt
def prices_publish(region, subregion):
    """Generate CPI dashboards.

    PoC scope: renders outputs/prices/eap_fnb_dashboard.html from the
    EAP F&B basket parquet. Region/subregion flags are accepted but
    ignored until the basket widens beyond the EAP PoC.
    """
    from prices.publish import run as _publish_run

    _publish_run()


@prices.command("consumable")
def prices_consumable():
    """Regenerate the curated ~10k consumable dataset family.

    Reads the `trusted` slice of the EAP F&B build and writes the
    outputs/prices/consumable_datasets/ parquets, coicop_titles.dta,
    Stata bundle, and README. No re-classify/re-embed — run after `build`.
    """
    from prices.build.consumable import run as _consumable_run

    _consumable_run()


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
