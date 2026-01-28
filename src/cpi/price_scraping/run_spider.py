#!/usr/bin/env python
"""
Convenience script to run Scrapy spiders with common configurations.
"""

import sys
import logging
import os
import json
from pathlib import Path

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

AVOID_SPIDERS = [
    "aeon_online",  # API -> does not have wayback machine yet
    "delishop_asia",  # API -> does not have wayback machine yet
]


def get_available_spiders():
    """
    Discover all available spiders in the project.

    Returns:
        List of spider names
    """
    from scrapy.utils.project import get_project_settings
    from scrapy.crawler import CrawlerRunner

    settings = get_project_settings()
    runner = CrawlerRunner(settings)

    spiders = []
    for spider_cls in runner.spider_loader.list():
        spiders.append(spider_cls)

    return spiders


def run_spider(spider_name: str, **kwargs):
    """
    Run a Scrapy spider with custom settings.

    Args:
        spider_name: Name of the spider to run (e.g., 'mh_online')
        **kwargs: Additional settings to override
    """
    # Get default settings
    settings = get_project_settings()

    # Override with custom settings
    for key, value in kwargs.items():
        settings.set(key, value)

    # Create crawler process
    process = CrawlerProcess(settings)

    try:
        # Check if spider is active before running
        from scrapy.crawler import CrawlerRunner

        runner = CrawlerRunner(settings)
        spider_cls = runner.spider_loader.load(spider_name)

        if hasattr(spider_cls, "active") and not spider_cls.active:
            logger.warning(
                f"Spider {spider_name} is inactive (active=False). Skipping."
            )
            return

        logger.info(f"Starting spider: {spider_name}")
        process.crawl(spider_name)
        process.start()
        logger.info(f"Spider {spider_name} completed successfully")
    except Exception as e:
        logger.error(f"Error running spider {spider_name}: {e}")
        sys.exit(1)


def run_all_spiders(**kwargs):
    """
    Run all available spiders sequentially with custom settings.

    Args:
        **kwargs: Additional settings to override
    """
    # Get default settings
    settings = get_project_settings()

    # Override with custom settings
    for key, value in kwargs.items():
        settings.set(key, value)

    # Create crawler process
    process = CrawlerProcess(settings)

    try:
        # Get all available spiders
        from scrapy.utils.project import get_project_settings as get_settings

        temp_settings = get_settings()
        from scrapy.crawler import CrawlerRunner

        runner = CrawlerRunner(temp_settings)
        spider_names = runner.spider_loader.list()

        logger.info(f"Found {len(spider_names)} spiders: {', '.join(spider_names)}")

        # Filter out inactive spiders and add active ones to the process
        active_spiders = []
        inactive_spiders = []

        for spider_name in spider_names:
            spider_cls = runner.spider_loader.load(spider_name)
            if hasattr(spider_cls, "active") and not spider_cls.active:
                inactive_spiders.append(spider_name)
                logger.info(f"Skipping inactive spider: {spider_name}")
            else:
                active_spiders.append(spider_name)
                logger.info(f"Scheduling spider: {spider_name}")
                process.crawl(spider_name)

        if inactive_spiders:
            logger.info(
                f"Skipped {len(inactive_spiders)} inactive spiders: {', '.join(inactive_spiders)}"
            )

        if not active_spiders:
            logger.warning("No active spiders to run")
            return

        # Run all active spiders
        logger.info(f"Starting {len(active_spiders)} active spiders...")
        process.start()
        logger.info("All spiders completed successfully")
    except Exception as e:
        logger.error(f"Error running spiders: {e}")
        sys.exit(1)


def load_scraped_items(output_dir: Path, spider_name: str, country: str) -> list:
    """
    Load all scraped items from JSONL files for a spider.

    Args:
        output_dir: Base output directory
        spider_name: Name of the spider
        country: Country code for directory structure

    Returns:
        List of items from all JSONL files
    """
    items = []
    spider_dir = output_dir / country / spider_name / "raw_items"

    if not spider_dir.exists():
        logger.warning(f"No raw items directory found at {spider_dir}")
        return items

    # Load all JSONL files
    for jsonl_file in spider_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        items.append(json.loads(line))
            logger.info(f"Loaded {len(items)} items from {jsonl_file}")
        except Exception as e:
            logger.error(f"Error loading {jsonl_file}: {e}")

    return items


def get_spider_country(spider_name: str) -> str:
    """
    Get the country code for a spider.

    Args:
        spider_name: Name of the spider

    Returns:
        Country code
    """
    spider_countries = {
        "rbpatel": "fiji",
        "mh_online": "fiji",
        "aldi_au": "australia",
        "food_pro": "papua_new_guinea",
        "molisi": "tonga",
        "samoa_market": "samoa",
        "dynamic_vanuatu": "vanuatu",
        "horizon_farms": "japan",
        "hypermart": "indonesia",
        "pickaroo": "philippines",
        "delishop_asia": "cambodia",
        "aeon_online": "cambodia",
        "makro": "cambodia",
        "thai_huot": "cambodia",
        "tiki": "vietnam",
        "rakuten": "japan",
        "yahoo_shopping": "japan",
    }
    return spider_countries.get(spider_name, "unknown")


def run_wayback_scraping(spider_name: str, output_dir: Path, from_date: str):
    """
    Run wayback machine scraping for a spider.

    Args:
        spider_name: Name of the spider
        output_dir: Base output directory
        from_date: End timestamp for wayback snapshots (YYYY-MM-DD format)
    """
    try:
        from price_scraping.wayback_scraper import WaybackScraper

        logger.info(f"Starting wayback machine scraping for {spider_name}")
        logger.info(f"Looking for snapshots up to {from_date}")

        # Get country code
        country = get_spider_country(spider_name)

        # Load scraped items
        items = load_scraped_items(output_dir, spider_name, country)
        if not items:
            logger.error(
                f"No items found for {spider_name} in {output_dir / country / spider_name / 'raw_items'}"
            )
            return

        logger.info(f"Loaded {len(items)} items for wayback scraping")

        # Run wayback scraper
        scraper = WaybackScraper(spider_name, output_dir, from_date)
        stats = scraper.run_scrape_wayback(items, country)

        # Log summary
        logger.info("=" * 60)
        logger.info("WAYBACK MACHINE SCRAPING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total items: {stats['total_items']}")
        logger.info(f"Unique URLs: {stats['unique_urls']}")
        logger.info(f"Successful scrapes: {stats['successful_scrapes']}")
        logger.info(f"Failed scrapes: {stats['failed_scrapes']}")
        logger.info(f"Total snapshots: {stats['total_snapshots']}")
        logger.info("=" * 60)

    except ImportError as e:
        logger.error(f"Failed to import wayback scraper: {e}")
        logger.error("Make sure waybackpy is installed: pip install waybackpy")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during wayback scraping: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    # Change to the script's directory so Scrapy can find scrapy.cfg
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    logger.info(f"Working directory: {os.getcwd()}")

    parser = argparse.ArgumentParser(description="Run Scrapy spiders")
    parser.add_argument("spider", nargs="?", help="Spider name to run")
    parser.add_argument("--all", action="store_true", help="Run all available spiders")
    parser.add_argument(
        "--delay", type=float, default=2, help="Download delay in seconds"
    )
    parser.add_argument("--concurrent", type=int, default=8, help="Concurrent requests")
    parser.add_argument(
        "--output-dir",
        default="data/cpi/price_scraping",
        help="Output directory for data",
    )
    parser.add_argument("--limit", type=int, help="Limit number of pages to crawl")
    parser.add_argument(
        "--scrape-wayback", action="store_true", help="Scrape wayback machine archives"
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        help="End timestamp for wayback snapshots (YYYY-MM-DD format)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.spider:
        parser.error("Either provide a spider name or use --all flag")

    # Validate wayback arguments
    if args.scrape_wayback and not args.from_date:
        parser.error("--from argument is required when using --scrape-wayback")

    # Convert output directory to absolute path if it's relative
    # This ensures output goes to the correct location regardless of where the script is called from
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        # If relative path, make it relative to the project root (parent of script directory)
        project_root = (
            script_dir.parent.parent.parent
        )  # src/cpi/price_scraping -> project root
        output_dir = project_root / output_dir

    logger.info(f"Output directory: {output_dir}")

    # If wayback scraping is requested, skip normal spider execution
    if args.scrape_wayback:
        if args.all:
            # Get all spider names
            from scrapy.utils.project import get_project_settings as get_settings

            temp_settings = get_settings()
            from scrapy.crawler import CrawlerRunner

            runner = CrawlerRunner(temp_settings)
            spider_names = runner.spider_loader.list()

            for spider_name in spider_names:
                if spider_name in AVOID_SPIDERS:
                    continue
                run_wayback_scraping(spider_name, output_dir, args.from_date)
        else:
            run_wayback_scraping(args.spider, output_dir, args.from_date)
    else:
        # Build settings dict
        settings_override = {
            "DOWNLOAD_DELAY": args.delay,
            "CONCURRENT_REQUESTS": args.concurrent,
            "OUTPUT_DIR": str(output_dir),
        }

        if args.limit:
            settings_override["CLOSESPIDER_PAGECOUNT"] = args.limit

        # Run spider(s)
        if args.all:
            run_all_spiders(**settings_override)
        else:
            run_spider(args.spider, **settings_override)
