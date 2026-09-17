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
from prices.cc_fleet_cli import cc_fleet_command as _prices_cc_fleet  # noqa: E402
from prices.cc_table_cli import cc_table_group as _prices_cc_table  # noqa: E402
from prices.enrich.cli import embed_command as _prices_embed  # noqa: E402
from prices.enrich.cli import process_command as _prices_process  # noqa: E402
from prices.enrich.eval.cli import eval_command as _prices_eval  # noqa: E402
from prices.enrich.match_record_view import (  # noqa: E402
    match_record_command as _prices_match_record,
)
from prices.enrich.census import census_command as _prices_census  # noqa: E402
from prices.enrich.coverage import coverage_command as _prices_coverage  # noqa: E402
from prices.enrich.port_decisions import (  # noqa: E402
    port_command as _prices_port_decisions,
)
from prices.enrich.classifier.cli import (  # noqa: E402
    train_classifier_command as _prices_train_classifier,
)
from prices.enrich.label_cli import label_group as _prices_label  # noqa: E402
from prices.enrich.gold_audit.cli import (  # noqa: E402
    gold_audit_group as _prices_gold_audit,
)

from prices.rtcal.cli import rtcal as _prices_rtcal  # noqa: E402
from prices.sanity import sanity_command as _prices_sanity  # noqa: E402
from prices.source_sanity import (  # noqa: E402
    source_sanity_command as _prices_source_sanity,
)

prices.add_command(_prices_collect, name="collect")
prices.add_command(_prices_backfill, name="backfill")
prices.add_command(_prices_common_crawl, name="common-crawl")
prices.add_command(_prices_cc_table, name="cc-table")
prices.add_command(_prices_cc_fleet, name="cc-fleet")
prices.add_command(_prices_process, name="process")
prices.add_command(_prices_embed, name="embed")
prices.add_command(_prices_eval, name="eval")
prices.add_command(_prices_match_record, name="match-record")
prices.add_command(_prices_census, name="census")
prices.add_command(_prices_coverage, name="coverage")
prices.add_command(_prices_port_decisions, name="port-decisions")
prices.add_command(_prices_train_classifier, name="train-classifier")
prices.add_command(_prices_label, name="label")
prices.add_command(_prices_gold_audit, name="gold-audit")
prices.add_command(_prices_rtcal, name="rtcal")
prices.add_command(_prices_sanity, name="sanity")
prices.add_command(_prices_source_sanity, name="source-sanity")


@prices.command("build")
@_region_opt
@_subregion_opt
@_country_opt
@click.option(
    "--only",
    multiple=True,
    metavar="SELECTOR",
    help=(
        "Recompute only part of the corpus, then overlay the result onto the "
        "full observations frame. A selector is a glob over "
        "region/subregion/country/source. Repeatable."
    ),
)
@click.option(
    "--recompute-leaf-tables",
    is_flag=True,
    default=None,
    help=(
        "Re-derive the typical-mass table from this run's rows. A scoped run "
        "pins it instead, because deriving it from a slice gives a leaf a mass "
        "the full build does not agree with."
    ),
)
@click.option(
    "--workers",
    type=int,
    default=1,
    show_default=True,
    help=(
        "Parallel shard workers for the observations join. Admission is by "
        "bytes in flight, not worker count, so the largest shards run alone "
        "rather than together."
    ),
)
def prices_build(region, subregion, country, only, recompute_leaf_tables, workers):
    """Construct CPI indices from the enriched prices dataset.

    PoC scope: writes the EAP × F&B basket parquet at
    data/prices/build/global_prices_observations.parquet.

    With --only (or -r/-S/-c) the observations pass recomputes just the
    selected countries and overlays them onto the existing frame, so the
    snapshot, summaries and dashboard still cover the whole corpus.
    """
    from prices import partition
    from prices.build.aggregate import run as _build_run

    selectors = list(only)
    from_flags = partition.selector_from_flags(region, subregion, country)
    if from_flags:
        selectors.append(from_flags)

    _build_run(
        selectors=selectors or None,
        recompute_leaf_tables=recompute_leaf_tables,
        workers=workers,
    )


_unfiltered_opt = click.option(
    "--unfiltered",
    is_flag=True,
    default=False,
    help=(
        "DIAGNOSTIC BUILD: take every minimum-evidence gate to its arithmetic "
        "floor. Output is renamed *_unfiltered.html and stamped with a banner; "
        "it can never overwrite a published dashboard."
    ),
)


def _set_unfiltered(on: bool) -> None:
    """Arm the gate profile BEFORE anything under `prices.` is imported.

    Every threshold in the prices dashboards is read once, at import of
    `prices.explorer.profile`, and taken by value from there by each consumer.
    That is what keeps the switch to one place instead of a conditional at every
    gate -- and it is why this has to run before the import below it, not after.
    """
    import os

    if on:
        os.environ["PO_PRICES_UNFILTERED"] = "1"


_window_opt = click.option(
    "--window-days",
    "window_days",
    type=int,
    default=None,
    metavar="N",
    help=(
        "Rolling window in days the 'current' cell grid is pooled over. "
        "Defaults to 90 (or $PO_PRICES_WINDOW_DAYS). A non-default window "
        "renames the output *_<N>d.html so two windows can never overwrite "
        "each other."
    ),
)


def _set_window_days(days: int | None) -> None:
    """Arm the window BEFORE anything under `prices.` is imported.

    Same reasoning as `_set_unfiltered`: `prices.explorer.sources.WINDOW_DAYS`
    is read once, at import, and `prices.publish` takes its own lookback from
    that same constant, so this has to run before either is imported.
    """
    import os

    if days is not None:
        os.environ["PO_PRICES_WINDOW_DAYS"] = str(days)


def _window_path(path, window_days: int):
    """`x.html` -> `x_30d.html` when the window isn't the default 90 days, so a
    narrower diagnostic build can never silently overwrite the default one.

    The 90 here is the same default as `sources.WINDOW_DAYS`, spelled again
    rather than imported: importing it would pull `prices.` in at module import
    of this file, which is precisely what `_set_window_days` has to run before.
    Change one and change the other."""
    if window_days == 90:
        return path
    return path.with_name(path.stem + f"_{window_days}d" + path.suffix)


@prices.command("fx-refresh")
@click.option("--cache", "cache_path", default=None, help="Override the FX cache path.")
@click.option(
    "--start",
    default=None,
    help="First date to fetch (default: day after the cache ends).",
)
@click.option("--end", default=None, help="Last date to fetch (default: today).")
def prices_fx_refresh(cache_path, start, end):
    """Extend the prices FX cache forward from Frankfurter v2.

    This is the ONLY prices command that fetches exchange rates. Build and
    publish read the cache and never touch the network, so a refresh is an
    explicit, reviewable step rather than a side effect of a build.
    """
    from prices.fx.paths import PRICES_FX_CACHE
    from prices.fx.refresh import refresh

    fetched = refresh(cache_path=cache_path or PRICES_FX_CACHE, start=start, end=end)
    click.echo(f"Fetched {fetched:,} FX rows.")


@prices.command("fx-rebuild")
@click.option(
    "--out", "out_path", required=True, help="Where to write the rebuilt cache."
)
@click.option("--start", default=None, help="History floor (default: 2013-01-01).")
@click.option("--end", default=None, help="Last date (default: today).")
@click.option(
    "--like",
    "like_cache",
    default=None,
    help="Take the currency list from this cache (default: the live one).",
)
def prices_fx_rebuild(out_path, start, end, like_cache):
    """Rebuild the whole FX history from Frankfurter v2 into a NEW file.

    --out is required and deliberately has no default: the live cache is the
    artifact the entire price corpus depends on, it is gitignored so it exists
    in exactly one place, and replacing it is a decision to be made after
    diffing, not a side effect of running this.
    """
    from prices.fx.paths import FX_HISTORY_FLOOR
    from prices.fx.refresh import rebuild

    frame = rebuild(
        out_path=out_path,
        start=start or FX_HISTORY_FLOOR,
        end=end,
        like_cache=like_cache,
    )
    click.echo(
        f"Wrote {len(frame):,} rows / {frame['currency'].nunique()} currencies "
        f"to {out_path}"
    )


@prices.command("fx-audit")
@click.option("--cache", "cache_path", default=None, help="Override the FX cache path.")
def prices_fx_audit(cache_path):
    """Report FX rates that are wrong by orders of magnitude.

    Flags a currency that steps and RETURNS, which is a merge artefact; a real
    redenomination steps and stays, and is not reported.
    """
    from prices.fx.audit import find_contaminated_blocks
    from prices.fx.cache import load_cache
    from prices.fx.paths import PRICES_FX_CACHE

    cache = load_cache(cache_path or PRICES_FX_CACHE)
    blocks = find_contaminated_blocks(cache)
    if blocks.empty:
        click.echo(f"No contaminated blocks in {len(cache):,} rows.")
        return
    click.echo(
        f"{len(blocks)} contaminated block(s) across "
        f"{blocks['currency'].nunique()} currencies:"
    )
    click.echo(blocks.to_string(index=False))


@prices.command("publish")
@_region_opt
@_subregion_opt
@click.option("--out", "out_path", default=None, help="Override the output HTML path.")
@_window_opt
@_unfiltered_opt
def prices_publish(region, subregion, out_path, window_days, unfiltered):
    """Generate CPI dashboards.

    PoC scope: renders outputs/prices/global_prices_dashboard.html from the
    EAP F&B basket parquet. With --region, restricts the build to that
    region's countries -- every downstream figure (KPIs, region/World
    medians, the low-coverage cutoff, the monthly series) is recomputed over
    just that set, so pair it with --out to avoid overwriting the
    unrestricted dashboard. --subregion is accepted but ignored until the
    basket widens beyond the EAP PoC.

    With --window-days, the "current" snapshot pools that many trailing days
    of prices instead of the default 90. `prices.explorer` and this dashboard
    share the one number, so both stay on the same definition of "current";
    a non-default window renames the output so a 30-day and a 90-day build
    can never collide.

    With --unfiltered every minimum-evidence gate goes to its arithmetic floor
    -- the lookback window opens to the whole corpus, the coverage floor to
    zero, and the qa_status=="trusted" restriction is lifted, so rows the QA
    layer rejected as wrong are drawn too. Diagnostic only.
    """
    import logging
    from pathlib import Path

    _set_unfiltered(unfiltered)
    _set_window_days(window_days)
    from prices.explorer.profile import unfiltered_path
    from prices.explorer.sources import WINDOW_DAYS
    from prices.publish import DASHBOARD_HTML
    from prices.publish import publish as _publish

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    out = unfiltered_path(
        _window_path(Path(out_path) if out_path else DASHBOARD_HTML, WINDOW_DAYS)
    )
    try:
        written = _publish(region=region, out_path=out)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if unfiltered:
        click.echo(f"UNFILTERED diagnostic build written to {written}")
    elif WINDOW_DAYS != 90:
        click.echo(f"{WINDOW_DAYS}-day window build written to {written}")


@prices.command("explorer")
@_region_opt
@click.option("--out", "out_path", default=None, help="Override the output HTML path.")
@_window_opt
@_unfiltered_opt
def prices_explorer(region, out_path, window_days, unfiltered):
    """Render the interactive unit-value explorer dashboard.

    Writes outputs/prices/global_prices_explorer.html from the build parquet:
    a world price-level ranking, a COICOP hierarchy browser, per-country
    profiles and a local/USD/FX decomposition. Self-contained, offline.

    With --region only that region's countries are shown, but every "vs world"
    yardstick stays global -- pair it with --out so the regional build does not
    overwrite the unrestricted one.

    With --window-days, the "current" cell grid pools that many trailing days
    of prices instead of the default 90 (shared with `prices publish` via
    $PO_PRICES_WINDOW_DAYS, so the two dashboards never disagree on what
    "current" means). A non-default window renames the output *_<N>d.html.

    With --unfiltered every minimum-evidence gate goes to its arithmetic floor,
    including the chain, geography and fixed-effect gates that decide a VALUE
    rather than a visibility. Those fits are unmeasured at their floor: a
    chained index may link on one pair and a period effect may be one item.
    Diagnostic only, renamed and banner-stamped so it cannot be mistaken for
    the real dashboard.
    """
    from pathlib import Path

    _set_unfiltered(unfiltered)
    _set_window_days(window_days)
    from prices.explorer import run as _explorer_run
    from prices.explorer.profile import stamp_unfiltered, unfiltered_path
    from prices.explorer.render import OUT_HTML
    from prices.explorer.sources import WINDOW_DAYS

    out = unfiltered_path(
        _window_path(Path(out_path) if out_path else OUT_HTML, WINDOW_DAYS)
    )
    written = _explorer_run(out, region)
    # The explorer's renderer is not this profile's to edit, so the banner goes
    # on afterwards, to the file. A no-op on a normal build; on an unfiltered
    # one it raises rather than leaving the page unstamped.
    stamp_unfiltered(written or out)
    if unfiltered:
        click.echo(f"UNFILTERED diagnostic build written to {written or out}")
    elif WINDOW_DAYS != 90:
        click.echo(f"{WINDOW_DAYS}-day window build written to {written or out}")


@prices.command("basket-weights")
def prices_basket_weights():
    """Refresh the expenditure-weight table behind the basket comparison.

    Writes data/prices/weights/expenditure_weights.csv -- one tidy
    (iso3, code, value, round, source) row per economy and COICOP category,
    from two sources that answer different halves of the same question:

      icp         World Bank ICP household final consumption expenditure, at
                  COICOP class depth for food and group depth for beverages,
                  alcohol and tobacco. This is what the default weights are
                  built from. Latest round available per economy, with no
                  vintage floor -- the alternative drops Macao, which is the
                  country the weights exist to fix.

      imf_wgt_pt  the countries' own published CPI weights by division, from
                  the same IMF dataset the CPI benchmark already uses. Stored
                  as an alternative division split, not used by default: one
                  source per tree, because ICP's shares nest and a mixture of
                  two sources' shares does not.

    Standalone, like cpi-benchmark: the explorer build reads the CSV directly.
    Network required for the refresh and never for the render -- a build with
    no table falls back to equal weight per category and says so in the
    payload.
    """
    import logging

    from prices.explorer.sources import load_taxonomy
    from prices.explorer.weights import default_weights, refresh

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tax = load_taxonomy()
    divisions = sorted(c for c, m in tax.items() if m.get("lvl") == 1)
    path = refresh(divisions)
    weights, meta = default_weights(tax, 3)
    click.echo(f"wrote {path}")
    click.echo(f"  {meta['label']}")
    click.echo(f"  rounds: {meta.get('rounds', {})}")
    click.echo(f"  {len(weights)} categories carry a default weight")
    for code, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        click.echo(
            f"    {code:<9}{(tax.get(code, {}).get('t') or '')[:44]:<46}"
            f"{w * 100:6.2f}%"
        )


@prices.command("ppp-benchmark")
def prices_ppp_benchmark():
    """Refresh the external price-level benchmark behind the basket ranking.

    Writes data/prices/ppp/price_level_benchmark.csv -- one tidy
    (iso3, code, value, round, source) row per economy and category, from two
    independently-produced price levels that our own ranking is checked
    against and never corrected by:

      icp   World Bank ICP `PX.WL`, price level index, WORLD = 100, at the same
            classification the expenditure weights come from: our nine food
            classes, non-alcoholic beverages, alcohol, tobacco, and the two
            division aggregates that are COICOP 01 and 02 exactly. Same base,
            same scope, same aggregation as the basket ranking. Latest round
            per economy with no vintage floor, and the round year is stored so
            a 2011 benchmark reads as one on screen.

      wdi   `PA.NUS.GDP.PLI` and `PA.NUS.PRVT.PLI`, price level index, UNITED
            STATES = 100, annual and extrapolated to the current year. This is
            what `PA.NUS.PPPC.RF` became -- that indicator is retired. Whole
            economy, so it prices rent and services alongside bread; carried
            because its vintage is current where ICP's is 2021.

    Standalone, like cpi-benchmark: the explorer build reads the CSV directly.
    Network required for the refresh and never for the render -- a build with
    no table draws the ranking without the benchmark chart.
    """
    import logging

    from prices.explorer.ppp import load_benchmark, refresh
    from prices.explorer.sources import (
        BASKET_WEIGHT_LEVEL,
        load_country_meta,
        load_taxonomy,
    )
    from prices.explorer.weights import default_weights

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    path = refresh()
    tax = load_taxonomy()
    weights, _ = default_weights(tax, BASKET_WEIGHT_LEVEL)
    meta = load_country_meta()
    got, prov = load_benchmark({s: m["iso3"] for s, m in meta.items()}, weights)
    click.echo(f"wrote {path}")
    click.echo(f"  {len(meta)} explorer countries")
    click.echo(
        f"  {prov['n_icp']} with an ICP food-and-tobacco price level " f"(World = 100)"
    )
    click.echo(
        f"  {prov['n_wdi']} with a WDI whole-economy price level "
        f"(rescaled by {prov['us_on_world']})"
    )
    rounds = {}
    for v in got.values():
        if v.get("icpYear"):
            rounds[v["icpYear"]] = rounds.get(v["icpYear"], 0) + 1
    click.echo(f"  ICP rounds: {dict(sorted(rounds.items()))}")


@prices.command("cpi-benchmark")
@_region_opt
def prices_cpi_benchmark(region):
    """Refresh the official-CPI benchmark table from the IMF.

    Writes data/cpi/official_cpi_monthly.csv -- one tidy
    (iso3, period, series, index_value) row per country, month and COICOP
    division, at whatever granularity the IMF publishes for that country
    (CP01..CP12 plus _T for all items). Standalone: the explorer build reads
    this file directly, so nothing in the enrich pipeline is involved.

    Responses are cached per country under data/cpi/imf/, so a re-run only
    fetches what is missing. Network required.
    """
    import logging

    from prices.explorer.cpi import refresh
    from prices.explorer.sources import load_country_meta

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    meta = load_country_meta()
    if region:
        from prices.explorer.aggregate import _region_label

        label = _region_label(region)
        meta = {s: m for s, m in meta.items() if m["region"] == label}
    iso3s = sorted({m["iso3"] for m in meta.values() if m["iso3"]})
    if not iso3s:
        raise click.ClickException("no countries selected")
    out = refresh(iso3s)
    click.echo(
        f"{len(out):,} rows · {out.iso3.nunique()} countries · "
        f"{out.series.nunique()} COICOP series"
    )


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
