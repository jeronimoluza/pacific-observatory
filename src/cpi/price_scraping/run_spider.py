#!/usr/bin/env python
"""
Convenience script to run Scrapy spiders with common configurations.
"""

import sys
import logging
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


def get_available_spiders():
    """
    Discover all available spiders in the project.
    
    Returns:
        List of spider names
    """
    from scrapy.utils.project import get_project_settings
    from scrapy.crawler import CrawlerRunner
    from twisted.internet import reactor
    
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
        
        # Add all spiders to the process
        for spider_name in spider_names:
            logger.info(f"Scheduling spider: {spider_name}")
            process.crawl(spider_name)
        
        # Run all spiders
        logger.info("Starting all spiders...")
        process.start()
        logger.info("All spiders completed successfully")
    except Exception as e:
        logger.error(f"Error running spiders: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Scrapy spiders")
    parser.add_argument("spider", nargs="?", help="Spider name to run")
    parser.add_argument(
        "--all", action="store_true", help="Run all available spiders"
    )
    parser.add_argument(
        "--delay", type=float, default=2, help="Download delay in seconds"
    )
    parser.add_argument(
        "--concurrent", type=int, default=8, help="Concurrent requests"
    )
    parser.add_argument(
        "--output-dir", default="data", help="Output directory for data"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of pages to crawl"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.spider:
        parser.error("Either provide a spider name or use --all flag")

    # Build settings dict
    settings_override = {
        "DOWNLOAD_DELAY": args.delay,
        "CONCURRENT_REQUESTS": args.concurrent,
        "OUTPUT_DIR": args.output_dir,
    }

    if args.limit:
        settings_override["CLOSESPIDER_PAGECOUNT"] = args.limit

    # Run spider(s)
    if args.all:
        run_all_spiders(**settings_override)
    else:
        run_spider(args.spider, **settings_override)
