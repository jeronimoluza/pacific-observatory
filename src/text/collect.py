"""Text collect stage: scrape new articles from configured newspapers."""

import logging
import os
from pathlib import Path

import click
import pandas as pd

from core.config import discover_pipeline_configs, parse_config_path
from core.logging import setup_logger
from core.state import read_state, write_state, set_checked

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
STATE_FILE = Path("data/text/.state.json")
DATA_BASE = Path("data/text")
LOGS_BASE = Path("logs")


def _source_stats(news_csv: Path) -> dict:
    """Read article count, date range, and file freshness from a news.csv file."""
    empty = {
        "article_count": "—",
        "earliest_date": "—",
        "last_date": "—",
        "last_updated": "—",
        "mtime": None,
    }
    if not news_csv.exists():
        return empty
    try:
        df = pd.read_csv(news_csv, usecols=["date"], dtype=str)
        if df.empty:
            return {**empty, "article_count": "0"}
        dates = df["date"].dropna()
        count = str(len(df))
        earliest = (dates.min() or "—")[:10] if not dates.empty else "—"
        last = (dates.max() or "—")[:10] if not dates.empty else "—"

        # File modification time → "YYYY-MM-DD HH:MM (Xd Yh ago)"
        from datetime import datetime, timezone

        mtime = datetime.fromtimestamp(news_csv.stat().st_mtime, tz=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - mtime
        days, hours = delta.days, delta.seconds // 3600
        if days > 0:
            ago = f"{days}d {hours}h ago"
        else:
            ago = f"{hours}h ago"
        updated = f"{mtime.strftime('%Y-%m-%d %H:%M')} ({ago})"

        return {
            "article_count": count,
            "earliest_date": earliest,
            "last_date": last,
            "last_updated": updated,
            "mtime": mtime,
        }
    except Exception:
        return {**{k: "?" for k in empty}, "mtime": None}


def _parse_article_count(raw: str) -> int:
    """Convert article_count string to int, treating '—' and '?' as 0."""
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


def _list_country_folders(country_dir: Path) -> list[str]:
    """Return sorted child directory names for a country data folder."""
    if not country_dir.exists():
        return []
    return sorted([p.name for p in country_dir.iterdir() if p.is_dir()])


def _format_mismatch(entry: dict) -> str:
    observed = entry.get("mismatch_observed") or []
    observed_str = ", ".join(observed) if observed else "(none)"
    return (
        f"{entry['region']}/{entry['subregion']}/{entry['country']}: "
        f"expected '{entry['data_folder_expected']}', found '{observed_str}'"
    )


def display_list(region=None, subregion=None, country=None, source=None):
    """Show YAML-only source inventory grouped by subregion/country. No CSV reads."""
    from itertools import groupby

    configs = discover_pipeline_configs(
        CONFIGS_DIR, region=region, subregion=subregion, country=country
    )
    if source:
        configs = [c for c in configs if c.stem == source]

    if not configs:
        click.echo("No sources found matching filters.")
        return

    entries = []
    for config_path in configs:
        rgn, subrgn, ctry = parse_config_path(config_path, CONFIGS_DIR)
        entries.append(
            {
                "region": rgn,
                "subregion": subrgn,
                "country": ctry,
                "source_key": config_path.stem,
            }
        )

    click.echo()
    click.echo(f"  {len(entries)} configured sources")
    click.echo("  A source is a configured newspaper. Use --source <key> to run one.")
    click.echo()

    entries_sorted = sorted(
        entries, key=lambda e: (e["region"], e["subregion"], e["country"])
    )
    for (rgn, subrgn), group in groupby(
        entries_sorted, key=lambda e: (e["region"], e["subregion"])
    ):
        click.echo(f"  {rgn} / {subrgn}")
        for ctry, country_group in groupby(list(group), key=lambda e: e["country"]):
            keys = [e["source_key"] for e in country_group]
            click.echo(f"    {ctry}   {' · '.join(keys)}")
        click.echo()

    click.echo("  Run 'po text status' for article counts and freshness.")
    click.echo("  Use --source <key> to run a single source.")
    click.echo()


def display_status(region=None, subregion=None, country=None, show_all=False):
    """Show per-source health table with article counts and freshness."""
    from datetime import datetime, timezone
    from itertools import groupby

    plan = _build_plan(region=region, subregion=subregion, country=country)
    if not plan:
        click.echo("No sources found matching filters.")
        return

    total = len(plan)
    scraped = sum(1 for e in plan if e["article_count"] not in ("—", "?"))
    total_articles = sum(_parse_article_count(e["article_count"]) for e in plan)
    countries_count = len(set(e["country"] for e in plan))
    mismatches = [e for e in plan if e.get("mismatch_observed")]

    if not show_all:
        plan = [e for e in plan if e["article_count"] not in ("—", "?")]
        if not plan:
            if mismatches:
                click.echo("\n  Warning: data folder name mismatches detected")
                for entry in mismatches:
                    click.echo(f"  - {_format_mismatch(entry)}")
            click.echo(f"\n  No scraped sources found ({total} configured).")
            click.echo("  Use --all to include unscraped sources.\n")
            return

    if mismatches:
        click.echo("\n  Warning: data folder name mismatches detected")
        for entry in mismatches:
            click.echo(f"  - {_format_mismatch(entry)}")
        click.echo(
            "  Rename folders manually under data/text/ to match config filenames."
        )
    if mismatches:
        click.echo("\n  Warning: data folder name mismatches detected")
        for entry in mismatches:
            click.echo(f"  - {_format_mismatch(entry)}")

    click.echo()
    click.echo(
        f"  Text Pipeline Status  ({total} sources · {scraped} scraped · "
        f"{total_articles:,} articles · {countries_count} countries)"
    )

    plan_sorted = sorted(
        plan, key=lambda e: (e["region"], e["subregion"], e["country"], e["newspaper"])
    )
    nw = max(25, max(len(e["newspaper"]) for e in plan) + 1)
    cw = max(18, max(len(e["country"]) for e in plan) + 1)

    for (rgn, subrgn), group in groupby(
        plan_sorted, key=lambda e: (e["region"], e["subregion"])
    ):
        entries = list(group)
        click.echo()
        click.echo(f"  {rgn} / {subrgn}")
        w = cw + nw + 8 + 24 + 16 + 8
        click.echo("  " + "─" * w)
        click.echo(
            f"  {'Country':<{cw}} {'Newspaper':<{nw}} {'Articles':>8}  "
            f"{'Coverage':>22}  {'Last Scraped':<16}"
        )
        click.echo("  " + "─" * w)

        sub_countries = set()
        sub_articles = 0
        for entry in entries:
            sub_countries.add(entry["country"])
            sub_articles += _parse_article_count(entry["article_count"])

            e_date = entry["earliest_date"]
            l_date = entry["last_date"]
            if e_date != "—" and l_date != "—":
                coverage = f"{e_date} → {l_date}"
            else:
                coverage = "—"

            mtime = entry.get("mtime")
            if mtime:
                delta = datetime.now(tz=timezone.utc) - mtime
                days, hours = delta.days, delta.seconds // 3600
                last_scraped = f"{days}d {hours}h ago" if days > 0 else f"{hours}h ago"
            else:
                last_scraped = "never"

            click.echo(
                f"  {entry['country']:<{cw}} "
                f"{entry['newspaper']:<{nw}} "
                f"{entry['article_count']:>8}  "
                f"{coverage:>22}  "
                f"{last_scraped:<16}"
            )

        click.echo("  " + "─" * w)
        click.echo(
            f"  {len(sub_countries)} countries · {len(entries)} sources · "
            f"{sub_articles:,} articles"
        )

    if not show_all and scraped < total:
        click.echo(
            f"\n  Showing {scraped} scraped sources of {total} configured. "
            f"Use --all to include all."
        )
    click.echo()


def _build_plan(region=None, subregion=None, country=None, source=None):
    """Discover configs and build execution plan with data stats."""
    from collections import defaultdict

    configs = discover_pipeline_configs(
        CONFIGS_DIR, region=region, subregion=subregion, country=country
    )
    if source:
        configs = [c for c in configs if c.stem == source]

    configs_by_country = defaultdict(list)
    for config_path in configs:
        cfg_region, cfg_subregion, cfg_country = parse_config_path(
            config_path, CONFIGS_DIR
        )
        configs_by_country[(cfg_region, cfg_subregion, cfg_country)].append(config_path)

    country_folder_info = {}
    for (cfg_region, cfg_subregion, cfg_country), paths in configs_by_country.items():
        expected = {p.stem for p in paths}
        country_dir = DATA_BASE / cfg_region / cfg_subregion / cfg_country
        actual = _list_country_folders(country_dir)
        extras = [name for name in actual if name not in expected]
        country_folder_info[(cfg_region, cfg_subregion, cfg_country)] = {
            "expected": expected,
            "actual": actual,
            "extras": extras,
        }

    plan = []
    for config_path in configs:
        cfg_region, cfg_subregion, cfg_country = parse_config_path(
            config_path, CONFIGS_DIR
        )
        newspaper = config_path.stem
        news_csv = (
            DATA_BASE
            / cfg_region
            / cfg_subregion
            / cfg_country
            / newspaper
            / "news.csv"
        )
        stats = _source_stats(news_csv)
        folder_info = country_folder_info.get(
            (cfg_region, cfg_subregion, cfg_country), {}
        )
        actual = folder_info.get("actual", [])
        extras = folder_info.get("extras", [])
        mismatch_observed = []
        if actual and newspaper not in actual and extras:
            mismatch_observed = extras

        plan.append(
            {
                "config_path": config_path,
                "region": cfg_region,
                "subregion": cfg_subregion,
                "country": cfg_country,
                "newspaper": newspaper,
                "source_key": newspaper,
                "data_folder_expected": newspaper,
                "mismatch_observed": mismatch_observed,
                **stats,
            }
        )
    return plan


def display_plan(plan, max_pages=None, max_articles=None, rebuild=False, region=None):
    """Show what collect will do."""
    if not plan:
        click.echo("No configs found matching filters.")
        return

    mismatches = [e for e in plan if e.get("mismatch_observed")]
    if mismatches:
        click.echo("\n  Warning: data folder name mismatches detected")
        for entry in mismatches:
            click.echo(f"  - {_format_mismatch(entry)}")
        click.echo(
            "  Rename folders manually under data/text/ to match config filenames."
        )

    # Descriptive header
    scope = region or "all"
    parts = [f"{len(plan)} newspapers", "newest -> oldest"]
    if max_pages:
        parts.append(f"{max_pages} pages max")
    if max_articles:
        parts.append(f"{max_articles} articles max")
    header = f"Collecting {scope} articles ({', '.join(parts)})"

    click.echo()
    click.echo(f"  {header}")
    if rebuild:
        click.echo("  WARNING: --rebuild will re-scrape and overwrite existing data")
    # Compute newspaper column width from longest name (min 25)
    nw = max(25, max(len(e["newspaper"]) for e in plan) + 1)
    w = nw + 18 + 8 + 10 + 10 + 26 + 12  # col widths + spacing
    click.echo("  " + "-" * w)
    click.echo(
        f"  {'Newspaper':<{nw}} {'Country':<18} {'Articles':>8}  "
        f"{'Earliest':>10}  {'Last Date':>10}  {'Last Updated':<26}"
    )
    click.echo("  " + "-" * w)
    for entry in plan:
        click.echo(
            f"  {entry['newspaper']:<{nw}} "
            f"{entry['country']:<18} "
            f"{entry['article_count']:>8}  "
            f"{entry['earliest_date']:>10}  "
            f"{entry['last_date']:>10}  "
            f"{entry['last_updated']:<26}"
        )
    click.echo()


def _print_source_summary(results):
    """Print categorized outcome summary for a single source."""
    stats = results.get("statistics", {})
    lines = [
        ("Thumbnails Discovered", stats.get("new_urls_discovered", 0)),
        ("Articles Scraped", stats.get("articles_scraped", 0)),
        ("Filtered (listing.filters)", stats.get("filtered_listing", 0)),
        ("Warning (empty tags)", stats.get("warning_tags", 0)),
        ("Warning (empty title)", stats.get("warning_title", 0)),
        ("Failed (empty body)", stats.get("failed_body", 0)),
        ("Failed (empty date)", stats.get("failed_date", 0)),
        ("Failed (HTTP error)", stats.get("failed_http", 0)),
    ]
    for label, count in lines:
        # Always show Thumbnails Discovered and Articles Scraped; skip zeros for the rest
        if count or label in ("Thumbnails Discovered", "Articles Scraped"):
            click.echo(f"  {label + ':':<30} {count:>5}")


def run_collect(
    region=None,
    subregion=None,
    country=None,
    source=None,
    max_pages=None,
    max_articles=None,
    dry_run=False,
    yes=False,
    rebuild=False,
    list_sources=False,
):
    """Run the text collect stage."""
    if list_sources:
        display_list(region=region, subregion=subregion, country=country, source=source)
        return

    plan = _build_plan(
        region=region, subregion=subregion, country=country, source=source
    )

    display_plan(
        plan,
        max_pages=max_pages,
        max_articles=max_articles,
        rebuild=rebuild,
        region=region,
    )

    if not plan:
        return

    if dry_run:
        click.echo("  Dry run -- no data collected.")
        return

    if not yes:
        click.confirm("  Proceed?", abort=True)

    # Import here to avoid errors when scraper code isn't migrated yet
    try:
        from text.scrapers.factory import create_scraper_from_file
    except ImportError:
        click.echo("  Error: scraper framework not yet migrated.")
        return

    import asyncio

    import warnings

    # Suppress scraper module logs from terminal — they use text.scrapers.* loggers
    # which propagate to root's lastResort handler (WARNING+ to stderr).
    # The po.text.{source} logger from setup_logger() is a separate hierarchy, unaffected.
    _scraper_log = logging.getLogger("text")
    _scraper_log.propagate = False
    _scraper_log.addHandler(logging.NullHandler())
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)

    # Suppress Python warnings from 3rd-party libs (BeautifulSoup XML, codec errors)
    warnings.filterwarnings("ignore")

    state = read_state(STATE_FILE)

    for entry in plan:
        newspaper = entry["newspaper"]
        rgn = entry["region"]
        subrgn = entry["subregion"]
        ctry = entry["country"]
        click.echo(f"\n  --- {newspaper} ({ctry}) ---")

        # Set up per-source logging: logs/text/{region}/{subregion}/{country}/{newspaper}/
        source_logger = setup_logger(
            pipeline="text",
            region=rgn,
            subregion=subrgn,
            country=ctry,
            source=newspaper,
            logs_dir=LOGS_BASE,
        )
        # Silence setup_logger's StreamHandler — collect.py handles CLI output via click
        for h in source_logger.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                h.setLevel(logging.CRITICAL)

        # Set data path: data/text/{region}/{subregion}/{country}/{newspaper}/
        # CSVStorage reads DATA_FOLDER_PATH env var for its base dir
        subregion_data_dir = str(DATA_BASE / rgn / subrgn)
        os.environ["DATA_FOLDER_PATH"] = subregion_data_dir

        try:
            scraper = create_scraper_from_file(str(entry["config_path"]))

            # Override max_pages/max_articles if CLI flags set.
            # Must also patch the listing_strategy since it captured
            # max_pages at construction time from config.
            if max_pages is not None:
                scraper.max_pages = max_pages
                if hasattr(scraper, "listing_strategy") and scraper.listing_strategy:
                    scraper.listing_strategy.max_pages = max_pages
            if max_articles is not None:
                scraper.max_articles = max_articles

            source_logger.info(
                "Starting %s for %s (%s/%s/%s)",
                "rebuild" if rebuild else "collect",
                newspaper,
                rgn,
                subrgn,
                ctry,
            )
            if rebuild:
                results = asyncio.run(scraper.run_full_scrape())
            else:
                results = asyncio.run(scraper.run_default())

            set_checked(state, entry["source_key"])
            source_logger.info("Done: %s", newspaper)
            _print_source_summary(results)

        except Exception as e:
            source_logger.exception("Failed: %s", newspaper)
            click.echo(f"  Failed: {newspaper} -- {e}")
            set_checked(state, entry["source_key"])

    write_state(state, STATE_FILE)
    click.echo("\n  Collection complete.")
