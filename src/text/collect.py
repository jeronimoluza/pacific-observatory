"""Text collect stage: scrape new articles from configured newspapers."""

import logging
import os
from pathlib import Path

import click

from core.config import discover_pipeline_configs
from core.logging import setup_logger
from core.state import read_state, write_state, set_checked, assess_source

logger = logging.getLogger(__name__)

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"
STATE_FILE = Path("data/text/.state.json")
DATA_BASE = Path("data/text")
LOGS_BASE = Path("logs")


def _build_plan(region=None, country=None, source=None):
    """Discover configs and build execution plan with staleness info."""
    configs = discover_pipeline_configs(CONFIGS_DIR, region=region, country=country)
    if source:
        configs = [c for c in configs if c.stem == source]

    state = read_state(STATE_FILE)
    plan = []
    for config_path in configs:
        parts = config_path.relative_to(CONFIGS_DIR).parts
        cfg_region = parts[0] if len(parts) >= 3 else "unknown"
        cfg_country = parts[1] if len(parts) >= 3 else parts[0]
        newspaper = config_path.stem
        source_key = newspaper

        entry_state = state.get(source_key, {})
        status = assess_source(
            last_data_date=None,
            note=entry_state.get("note"),
        )
        last_date = entry_state.get("last_data_date") or "never"

        plan.append(
            {
                "config_path": config_path,
                "region": cfg_region,
                "country": cfg_country,
                "newspaper": newspaper,
                "source_key": source_key,
                "last_data_date": last_date,
                "status": status,
            }
        )
    return plan


def display_plan(plan, max_pages=None, max_articles=None):
    """Show what collect will do."""
    if not plan:
        click.echo("No configs found matching filters.")
        return

    click.echo()
    click.echo("  Text collection")
    click.echo("  " + "-" * 60)
    click.echo(f"  {'Newspaper':<30} {'Country':<15} {'Latest':<12} Status")
    click.echo("  " + "-" * 60)
    for entry in plan:
        click.echo(
            f"  {entry['newspaper']:<30} "
            f"{entry['country']:<15} "
            f"{entry['last_data_date']:<12} "
            f"{entry['status']}"
        )
    click.echo()
    click.echo(f"  {len(plan)} newspaper(s)")
    if max_pages:
        click.echo(f"  Limited to {max_pages} pages per newspaper")
    if max_articles:
        click.echo(f"  Limited to {max_articles} articles per newspaper")
    click.echo()


def run_collect(
    region=None,
    country=None,
    source=None,
    max_pages=None,
    max_articles=None,
    dry_run=False,
    yes=False,
):
    """Run the text collect stage."""
    plan = _build_plan(region=region, country=country, source=source)
    display_plan(plan, max_pages=max_pages, max_articles=max_articles)

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

            # Override max_pages/max_articles if CLI flags set
            if max_pages is not None:
                scraper.max_pages = max_pages
            if max_articles is not None:
                scraper.max_articles = max_articles

            source_logger.info("Starting collect for %s (%s/%s)", newspaper, rgn, ctry)
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
