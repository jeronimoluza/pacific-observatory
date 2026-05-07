#!/usr/bin/env python
"""
Convenience script to run Scrapy spiders with common configurations.
"""

import sys
import logging
import os
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

logger = logging.getLogger(__name__)


_RUN_LOG_STAMP: str | None = None
_LOG_PROJECT_ROOT: Path | None = None
_LOG_FORMATTER: logging.Formatter | None = None
_MASTER_LOG_PATH: Path | None = None
_SPIDER_LOG_HANDLERS: dict[str, logging.Handler] = {}


class _SpiderNameFilter(logging.Filter):
    def __init__(self, spider_name: str):
        super().__init__()
        self._spider_name = spider_name

    def filter(self, record: logging.LogRecord) -> bool:
        spider = getattr(record, "spider", None)
        if spider is None:
            # Some log records don't carry spider context; keep those in the master log only.
            return False

        if not isinstance(spider, str):
            spider = getattr(spider, "name", None)

        if spider is None:
            return False

        return spider == self._spider_name


def _get_project_root(script_dir: Path) -> Path:
    # src/cpi/price_scraping -> project root
    return script_dir.parent.parent.parent


def _setup_run_logging(project_root: Path, level: int = logging.INFO) -> None:
    """Configure a master log + per-spider logs under logs/price-atlas/."""

    global _RUN_LOG_STAMP, _LOG_PROJECT_ROOT, _LOG_FORMATTER, _MASTER_LOG_PATH

    if _RUN_LOG_STAMP is None:
        _RUN_LOG_STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    _LOG_PROJECT_ROOT = project_root

    root = logging.getLogger()
    root.setLevel(level)

    # Reset handlers to avoid duplicates if this module is imported/reused.
    for h in list(root.handlers):
        root.removeHandler(h)

    _LOG_FORMATTER = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [spider=%(spider)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        defaults={"spider": "-"},
    )

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(_LOG_FORMATTER)
    root.addHandler(stream)

    runs_dir = project_root / "logs" / "price-atlas" / "_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    _MASTER_LOG_PATH = runs_dir / f"{_RUN_LOG_STAMP}_run.log"

    master = logging.FileHandler(_MASTER_LOG_PATH, encoding="utf-8")
    master.setLevel(level)
    master.setFormatter(_LOG_FORMATTER)
    root.addHandler(master)


def _resolve_spider_country(spider_name: str) -> str:
    """Best-effort country lookup for log/output paths."""
    try:
        settings = get_project_settings()
        from scrapy.crawler import CrawlerRunner

        runner = CrawlerRunner(settings)
        spider_cls = runner.spider_loader.load(spider_name)
        country = getattr(spider_cls, "country", None)
        if isinstance(country, str) and country.strip():
            return country
    except Exception:
        pass

    # Fallback to legacy mapping.
    return get_spider_country(spider_name)


def _ensure_spider_log_handler(spider_name: str, level: int = logging.INFO) -> Path:
    if _RUN_LOG_STAMP is None or _LOG_PROJECT_ROOT is None or _LOG_FORMATTER is None:
        raise RuntimeError("Run logging is not initialized")

    if spider_name in _SPIDER_LOG_HANDLERS:
        # Best effort: return the existing path if it's a FileHandler.
        handler = _SPIDER_LOG_HANDLERS[spider_name]
        if isinstance(handler, logging.FileHandler):
            return Path(handler.baseFilename)
        return _LOG_PROJECT_ROOT / "logs" / "price-atlas" / "unknown" / spider_name

    country = _resolve_spider_country(spider_name)
    spider_dir = _LOG_PROJECT_ROOT / "logs" / "price-atlas" / country / spider_name
    spider_dir.mkdir(parents=True, exist_ok=True)
    log_path = spider_dir / f"{_RUN_LOG_STAMP}_run.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_LOG_FORMATTER)
    handler.addFilter(_SpiderNameFilter(spider_name))

    logging.getLogger().addHandler(handler)
    _SPIDER_LOG_HANDLERS[spider_name] = handler
    return log_path


def _spider_logger(spider_name: str) -> logging.LoggerAdapter:
    _ensure_spider_log_handler(spider_name)
    return logging.LoggerAdapter(logging.getLogger(__name__), {"spider": spider_name})


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

    spider_log = _spider_logger(spider_name)

    # Create crawler process (we manage root logging ourselves)
    process = CrawlerProcess(settings, install_root_handler=False)

    try:
        # Check if spider is active before running
        from scrapy.crawler import CrawlerRunner

        runner = CrawlerRunner(settings)
        spider_cls = runner.spider_loader.load(spider_name)

        if not bool(getattr(spider_cls, "active", True)):
            logger.warning(
                f"Spider {spider_name} is inactive (active=False). Skipping."
            )
            return

        spider_log.info(f"Starting spider: {spider_name}")
        process.crawl(spider_name)
        process.start()
        spider_log.info(f"Spider {spider_name} completed successfully")
    except Exception as e:
        spider_log.exception(f"Error running spider {spider_name}: {e}")
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

    # Create crawler process (we manage root logging ourselves)
    process = CrawlerProcess(settings, install_root_handler=False)

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
            if not bool(getattr(spider_cls, "active", True)):
                inactive_spiders.append(spider_name)
                logger.info(f"Skipping inactive spider: {spider_name}")
            else:
                active_spiders.append(spider_name)
                _ensure_spider_log_handler(spider_name)
                _spider_logger(spider_name).info(f"Scheduling spider: {spider_name}")
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
        # New spiders
        "jianke": "china",
        "pharmacy_111": "china",
        "mannings": "hong_kong",
        "citypharm": "mongolia",
        "cosmed": "taiwan",
        "k24klik": "indonesia",
        "guardian_my": "malaysia",
        "doctor_oncall": "malaysia",
        "south_star_drug": "philippines",
        "guardian_sg": "singapore",
        "fairprice": "singapore",
        "boots_th": "thailand",
        "exta": "thailand",
        # Tier 1 additions (2026-05-06)
        "citysuper_hk": "hong_kong",
        "cold_storage_sg": "singapore",
        "carrefour_tw": "taiwan",
        # Tier 2 stubs (active=False)
        "lotuss_my": "malaysia",
        "wellcome_hk": "hong_kong",
        "hktvmall_hk": "hong_kong",
        "lotuss_th": "thailand",
        "makro_pro_th": "thailand",
    }
    return spider_countries.get(spider_name, "unknown")


def get_first_scrape_date(
    spider_name: str, output_dir: Path, country: str
) -> str | None:
    """
    Get the first scrape date for a spider by finding earliest scraped_at timestamp.
    Returns date one day before first scrape for wayback machine scraping.

    Args:
        spider_name: Name of the spider
        output_dir: Base output directory
        country: Country code for directory structure

    Returns:
        Date string in YYYY-MM-DD format (one day before first scrape), or None if no data
    """
    items = load_scraped_items(output_dir, spider_name, country)

    if not items:
        logger.warning(f"No scraped items found for {spider_name}")
        return None

    # Extract all scraped_at timestamps
    timestamps = []
    for item in items:
        scraped_at = item.get("scraped_at")
        if scraped_at:
            try:
                # Parse various date formats
                # Examples: "Thu, 12 Feb 2026 22:03:15 GMT", "2026-02-12T22:03:15"
                dt = pd.to_datetime(scraped_at)
                # Convert to timezone-naive to avoid comparison issues
                if dt.tzinfo is not None:
                    dt = dt.tz_localize(None)
                timestamps.append(dt)
            except Exception as e:
                logger.debug(f"Could not parse timestamp {scraped_at}: {e}")
                continue

    if not timestamps:
        logger.warning(f"No valid timestamps found for {spider_name}")
        return None

    # Get earliest timestamp and subtract 1 day
    earliest = min(timestamps)
    from_date = earliest - pd.Timedelta(days=1)
    from_date_str = from_date.strftime("%Y-%m-%d")

    logger.info(
        f"Auto-detected first scrape date for {spider_name}: {earliest.strftime('%Y-%m-%d')}"
    )
    logger.info(f"Setting wayback --from date to: {from_date_str}")

    return from_date_str


def run_wayback_scraping(
    spider_name: str,
    output_dir: Path,
    from_date: str | None = None,
    since_date: str | None = None,
    fetcher_workers: int = 8,
    parser_workers: int = 8,
):
    """
    Run wayback machine scraping for a spider.

    Args:
        spider_name: Name of the spider
        output_dir: Base output directory
        from_date: End timestamp for wayback snapshots (YYYY-MM-DD format).
                   If None, auto-detects from first scrape date.
        since_date: Start timestamp for wayback snapshots (YYYY-MM-DD format).
                    If provided, restricts CDX query to snapshots on/after this date —
                    useful for recovering a specific gap window without re-fetching history.
    """
    try:
        from price_scraping.wayback_scraper import WaybackScraper

        spider_log = _spider_logger(spider_name)

        # Get country code
        country = _resolve_spider_country(spider_name)

        # Auto-detect from_date if not provided
        if from_date is None:
            spider_log.info(f"Auto-detecting --from date for {spider_name}...")
            from_date = get_first_scrape_date(spider_name, output_dir, country)
            if from_date is None:
                spider_log.error(
                    f"Could not auto-detect --from date for {spider_name}. "
                    f"No scraped data found or timestamps invalid."
                )
                return

        spider_log.info(f"Starting wayback machine scraping for {spider_name}")
        spider_log.info(f"Looking for snapshots up to {from_date}")

        # Load scraped items
        items = load_scraped_items(output_dir, spider_name, country)
        if not items:
            logger.error(
                f"No items found for {spider_name} in {output_dir / country / spider_name / 'raw_items'}"
            )
            return

        spider_log.info(f"Loaded {len(items)} items for wayback scraping")

        # Run wayback scraper
        scraper = WaybackScraper(
            spider_name, output_dir, from_date, since_date=since_date
        )
        stats = scraper.run_scrape_wayback(
            items,
            country,
            num_fetcher_workers=fetcher_workers,
            num_parser_workers=parser_workers,
        )

        # Log summary
        spider_log.info("=" * 60)
        spider_log.info("WAYBACK MACHINE SCRAPING SUMMARY")
        spider_log.info("=" * 60)
        spider_log.info(f"Total items: {stats['total_items']}")
        spider_log.info(f"Unique URLs: {stats['unique_urls']}")
        spider_log.info(f"Successful scrapes: {stats['successful_scrapes']}")
        spider_log.info(f"Failed scrapes: {stats['failed_scrapes']}")
        spider_log.info(f"Total snapshots: {stats['total_snapshots']}")
        spider_log.info("=" * 60)

    except ImportError as e:
        logger.error(f"Failed to import wayback scraper: {e}")
        logger.error("Make sure waybackpy is installed: pip install waybackpy")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during wayback scraping: {e}")
        sys.exit(1)


def run_cc_scraping(
    spider_name: str,
    output_dir: Path,
    cc_indexes: list[str],
    num_workers: int = 8,
):
    """
    Run Common Crawl WARC scraping for a spider.

    Args:
        spider_name: Name of the spider
        output_dir: Base output directory
        cc_indexes: List of CC index IDs (e.g. ['CC-MAIN-2024-22','CC-MAIN-2026-17'])
        num_workers: Concurrent WARC fetches per index
    """
    try:
        from price_scraping.cc_warc_fetcher import CommonCrawlScraper

        spider_log = _spider_logger(spider_name)
        country = _resolve_spider_country(spider_name)

        spider_log.info(
            f"Starting Common Crawl scraping for {spider_name} ({country}) "
            f"across {len(cc_indexes)} indexes"
        )
        spider_log.info(f"Indexes: {', '.join(cc_indexes)}")

        scraper = CommonCrawlScraper(spider_name, output_dir, cc_indexes)
        stats = scraper.run_scrape_cc(country, num_workers=num_workers)

        spider_log.info("=" * 60)
        spider_log.info("COMMON CRAWL SCRAPING SUMMARY")
        spider_log.info("=" * 60)
        for k, v in stats.items():
            spider_log.info(f"{k}: {v}")
        spider_log.info("=" * 60)

    except KeyError as e:
        logger.error(f"No CC config for spider: {e}")
        sys.exit(1)
    except ImportError as e:
        logger.error(f"Failed to import cc_warc_fetcher: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error during CC scraping: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    # Change to the script's directory so Scrapy can find scrapy.cfg
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    project_root = _get_project_root(script_dir)
    _setup_run_logging(project_root)
    logger.info(f"Working directory: {os.getcwd()}")
    if _MASTER_LOG_PATH is not None:
        logger.info(f"Master log: {_MASTER_LOG_PATH}")

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
        help="End timestamp for wayback snapshots (YYYY-MM-DD format). "
        "If not provided, auto-detects from first scrape date (first scrape - 1 day).",
    )
    parser.add_argument(
        "--since",
        dest="since_date",
        help="Start timestamp for wayback snapshots (YYYY-MM-DD format). "
        "Restricts CDX to snapshots on/after this date — use to recover a specific gap window.",
    )
    parser.add_argument(
        "--scrape-cc",
        action="store_true",
        help="Scrape Common Crawl WARC archives instead of running the spider live.",
    )
    parser.add_argument(
        "--cc-indexes",
        default="",
        help="Comma-separated CC index IDs (e.g. CC-MAIN-2024-22,CC-MAIN-2026-17). "
        "Required with --scrape-cc.",
    )
    parser.add_argument(
        "--cc-workers",
        type=int,
        default=8,
        help="Concurrent WARC fetches per index (default: 8).",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.all and not args.spider:
        parser.error("Either provide a spider name or use --all flag")

    # Note: --from argument is now optional for wayback scraping
    # If not provided, it will be auto-detected from first scrape date

    # Convert output directory to absolute path if it's relative
    # This ensures output goes to the correct location regardless of where the script is called from
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        # If relative path, make it relative to the project root
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
                run_wayback_scraping(
                    spider_name, output_dir, args.from_date, args.since_date
                )
        else:
            run_wayback_scraping(
                args.spider, output_dir, args.from_date, args.since_date
            )
    elif args.scrape_cc:
        cc_indexes = [s.strip() for s in args.cc_indexes.split(",") if s.strip()]
        if not cc_indexes:
            parser.error("--scrape-cc requires --cc-indexes <list>")
        if args.all:
            parser.error("--scrape-cc with --all is not supported; pass a spider name")
        run_cc_scraping(args.spider, output_dir, cc_indexes, args.cc_workers)
    else:
        # Build settings dict
        settings_override = {
            "DOWNLOAD_DELAY": args.delay,
            "CONCURRENT_REQUESTS": args.concurrent,
            "OUTPUT_DIR": str(output_dir),
            "LOG_STDOUT": True,
        }

        if args.limit:
            settings_override["CLOSESPIDER_PAGECOUNT"] = args.limit

        # Run spider(s)
        if args.all:
            run_all_spiders(**settings_override)
        else:
            run_spider(args.spider, **settings_override)
