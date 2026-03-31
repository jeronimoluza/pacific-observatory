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


def _source_stats(news_csv: Path) -> tuple[str, str]:
    """Read article count and max date from a news.csv file."""
    if not news_csv.exists():
        return "—", "—"
    try:
        df = pd.read_csv(news_csv, usecols=["date"], dtype=str)
        if df.empty:
            return "0", "—"
        count = str(len(df))
        last = df["date"].dropna().max() or "—"
        # Truncate to date portion if it's a full timestamp
        if isinstance(last, str) and len(last) > 10:
            last = last[:10]
        return count, last
    except Exception:
        return "?", "?"


def _build_plan(region=None, country=None, source=None):
    """Discover configs and build execution plan with data stats."""
    configs = discover_pipeline_configs(CONFIGS_DIR, region=region, country=country)
    if source:
        configs = [c for c in configs if c.stem == source]

    plan = []
    for config_path in configs:
        parts = config_path.relative_to(CONFIGS_DIR).parts
        cfg_region = parts[0] if len(parts) >= 3 else "unknown"
        cfg_country = parts[1] if len(parts) >= 3 else parts[0]
        newspaper = config_path.stem

        news_csv = DATA_BASE / cfg_region / cfg_country / newspaper / "news.csv"
        article_count, last_date = _source_stats(news_csv)

        plan.append(
            {
                "config_path": config_path,
                "region": cfg_region,
                "country": cfg_country,
                "newspaper": newspaper,
                "source_key": newspaper,
                "article_count": article_count,
                "last_date": last_date,
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
    click.echo("  " + "-" * 68)
    click.echo(
        f"  {'Newspaper':<30} {'Country':<15} {'Articles':>8}   {'Last date':<10}"
    )
    click.echo("  " + "-" * 68)
    for entry in plan:
        click.echo(
            f"  {entry['newspaper']:<30} "
            f"{entry['country']:<15} "
            f"{entry['article_count']:>8}   "
            f"{entry['last_date']:<10}"
        )
    click.echo()


def run_collect(
    region=None,
    country=None,
    source=None,
    max_pages=None,
    max_articles=None,
    dry_run=False,
    yes=False,
    rebuild=False,
):
    """Run the text collect stage."""
    plan = _build_plan(region=region, country=country, source=source)
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

    state = read_state(STATE_FILE)

    for entry in plan:
        newspaper = entry["newspaper"]
        rgn = entry["region"]
        ctry = entry["country"]
        click.echo(f"\n  --- {newspaper} ({ctry}) ---")

        # Set up per-source logging: logs/text/{region}/{country}/{newspaper}/
        source_logger = setup_logger(
            pipeline="text",
            region=rgn,
            country=ctry,
            source=newspaper,
            logs_dir=LOGS_BASE,
        )

        # Set data path: data/text/{region}/{country}/{newspaper}/
        # CSVStorage reads DATA_FOLDER_PATH env var for its base dir
        region_data_dir = str(DATA_BASE / rgn)
        os.environ["DATA_FOLDER_PATH"] = region_data_dir

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
                "Starting %s for %s (%s/%s)",
                "rebuild" if rebuild else "collect",
                newspaper,
                rgn,
                ctry,
            )
            if rebuild:
                asyncio.run(scraper.run_full_scrape())
            else:
                asyncio.run(scraper.run_default())

            set_checked(state, entry["source_key"])
            source_logger.info("Done: %s", newspaper)
            click.echo(f"  Done: {newspaper}")

        except Exception as e:
            source_logger.exception("Failed: %s", newspaper)
            click.echo(f"  Failed: {newspaper} -- {e}")
            set_checked(state, entry["source_key"])

    write_state(state, STATE_FILE)
    click.echo("\n  Collection complete.")
