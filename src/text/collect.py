"""Text collect stage: scrape new articles from configured newspapers."""

import logging
import os
from pathlib import Path

import click
import pandas as pd

from core.config import discover_pipeline_configs
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
        }
    except Exception:
        return {k: "?" for k in empty}


def _build_plan(region=None, subregion=None, country=None, source=None):
    """Discover configs and build execution plan with data stats."""
    configs = discover_pipeline_configs(
        CONFIGS_DIR, region=region, subregion=subregion, country=country
    )
    if source:
        configs = [c for c in configs if c.stem == source]

    plan = []
    for config_path in configs:
        parts = config_path.relative_to(CONFIGS_DIR).parts
        # Structure: {region}/{subregion}/{country}/{source}.yaml
        cfg_region = parts[0] if len(parts) >= 4 else "unknown"
        cfg_subregion = parts[1] if len(parts) >= 4 else "unknown"
        cfg_country = (
            parts[2] if len(parts) >= 4 else parts[1] if len(parts) >= 3 else parts[0]
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

        plan.append(
            {
                "config_path": config_path,
                "region": cfg_region,
                "subregion": cfg_subregion,
                "country": cfg_country,
                "newspaper": newspaper,
                "source_key": newspaper,
                **stats,
            }
        )
    return plan


def display_plan(plan, max_pages=None, max_articles=None, rebuild=False, region=None):
    """Show what collect will do."""
    if not plan:
        click.echo("No configs found matching filters.")
        return

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
):
    """Run the text collect stage."""
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
