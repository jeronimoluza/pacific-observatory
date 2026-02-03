#!/usr/bin/env python3
"""
Pacific Observatory - Text Scraping CLI Entry Point

This script provides a command-line interface for running newspaper scrapers
using the new config-driven architecture.

Usage:
    python src/text/scrapers/orchestration/main.py --help
    python src/text/scrapers/orchestration/main.py sibc
    python src/text/scrapers/orchestration/main.py --list-scrapers
    python src/text/scrapers/orchestration/main.py --list-countries
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# noqa: E402 - Add the src directory to Python path for imports
script_dir = Path(__file__).resolve().parent  # orchestration/
scrapers_dir = script_dir.parent  # scrapers/
text_dir = scrapers_dir.parent  # text/
src_dir = text_dir.parent  # src/

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Set up the data folder path
os.environ["DATA_FOLDER_PATH"] = "data/text"

from text.scrapers.orchestration.utils import (  # noqa: E402
    setup_logging,
    get_project_paths,
    get_default_configs_dir,
)
from text.scrapers.orchestration.discovery import (  # noqa: E402
    get_available_scrapers,
    get_available_countries,
)
from text.scrapers.orchestration.run_scraper import (  # noqa: E402
    run_scraper_by_name,
)
from text.scrapers.orchestration.run_multiple import (  # noqa: E402
    run_all_scrapers,
)

# Get project paths
paths = get_project_paths()
project_root = paths["project_root"]


def list_available_scrapers():
    """CLI wrapper: List all available newspaper scrapers."""
    scrapers = get_available_scrapers(get_default_configs_dir())

    if not scrapers:
        print("❌ No scrapers found")
        return

    print("📰 Available Newspaper Scrapers:")
    print("=" * 50)

    for country_name, newspapers in scrapers.items():
        print(f"\n🌍 {country_name.upper()}:")
        for newspaper_name in newspapers:
            print(f"  📄 {newspaper_name}")
            print(
                f"     Command: python src/text/scrapers/orchestration/main.py {newspaper_name}"
            )

    print("\n" + "=" * 50)


def list_countries():
    """CLI wrapper: List all available countries."""
    countries = get_available_countries(get_default_configs_dir())

    if not countries:
        print("❌ No countries found")
        return

    print("🌍 Available Countries:")
    print("=" * 30)
    for country in countries:
        print(f"  🏴 {country}")
    print("=" * 30)


def main():
    """Main entry point for the text scraping tools."""
    parser = argparse.ArgumentParser(
        description="Pacific Observatory - Newspaper Scraping Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default mode: discover new URLs + scrape pending articles
  python src/text/scrapers/orchestration/main.py sibc
  python src/text/scrapers/orchestration/main.py sibc --update

  # Resume mode: scrape pending articles from urls.csv (no discovery)
  python src/text/scrapers/orchestration/main.py sibc --resume

  # Full discovery mode: discover ALL URLs (overwrite urls.csv, no scraping)
  python src/text/scrapers/orchestration/main.py sibc --full-discovery

  # Full from scratch: discover ALL URLs + scrape everything
  python src/text/scrapers/orchestration/main.py sibc --full-from-scratch

  # Multi-scraper runner
  python src/text/scrapers/orchestration/main.py --run-all
  python src/text/scrapers/orchestration/main.py --run-all --resume
  python src/text/scrapers/orchestration/main.py --run-all --full-discovery
  python src/text/scrapers/orchestration/main.py --run-all --sequential
  python src/text/scrapers/orchestration/main.py --run-all --dry-run

  # List available scrapers
  python src/text/scrapers/orchestration/main.py --list-scrapers
  python src/text/scrapers/orchestration/main.py --list-countries
        """,
    )

    # Main arguments
    parser.add_argument("newspaper", nargs="?", help="Name of the newspaper to scrape")

    parser.add_argument(
        "--country", help="Country code filter (e.g., SB for Solomon Islands)"
    )

    # List options
    parser.add_argument(
        "--list-scrapers",
        action="store_true",
        help="List all available newspaper scrapers",
    )

    parser.add_argument(
        "--list-countries",
        action="store_true",
        help="List all available countries",
    )

    # Multi-scraper runner options
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all newspaper scrapers in parallel",
    )

    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential execution (for debugging, use with --run-all)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without actually running (use with --run-all)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Stale timeout in seconds - kill scraper if no activity for this long (default: 120)",
    )

    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated list of newspaper names to exclude (e.g., --exclude detik,kosmo)",
    )

    # Scraping options
    parser.add_argument(
        "--storage-dir", type=Path, help="Custom storage directory for results"
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to disk (dry run)",
    )

    # === Run Mode Flags ===
    # These 4 flags control what the scraper does (mutually exclusive)

    parser.add_argument(
        "--update",
        action="store_const",
        const="update",
        dest="mode",
        help="Discover new URLs + scrape only new articles (default Friday run)",
    )

    parser.add_argument(
        "--resume",
        action="store_const",
        const="resume",
        dest="mode",
        help="Use existing urls.csv + scrape pending articles (no discovery)",
    )

    parser.add_argument(
        "--full-discovery",
        action="store_const",
        const="full_discovery",
        dest="mode",
        help="Discover ALL URLs + overwrite urls.csv (no scraping)",
    )

    parser.add_argument(
        "--full-from-scratch",
        action="store_const",
        const="full_from_scratch",
        dest="mode",
        help="Discover ALL URLs + scrape everything (nuclear option)",
    )

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    parser.add_argument("--log-file", type=Path, help="Log file path")

    # Set default mode
    parser.set_defaults(mode="update")

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.log_level, args.log_file)

    # Get mode from args (defaults to "update" if not specified)
    mode = getattr(args, "mode", "update")

    # Handle list commands
    if args.list_scrapers:
        list_available_scrapers()
        return

    if args.list_countries:
        list_countries()
        return

    # Handle run-all command
    if args.run_all:
        # Parse exclude list
        exclude_list = []
        if args.exclude:
            exclude_list = [
                name.strip().lower() for name in args.exclude.split(",") if name.strip()
            ]
            if exclude_list:
                print(f"⏭️  Excluding scrapers: {', '.join(exclude_list)}")

        results = run_all_scrapers(
            configs_dir=get_default_configs_dir(),
            project_root=project_root,
            sequential=args.sequential,
            dry_run=args.dry_run,
            mode=mode,
            timeout_per_scraper=args.timeout,
            exclude=exclude_list,
        )
        # Exit with failure if any scraper failed or timed out
        failed_count = sum(
            1 for r in results if r.get("status") in ["failed", "timeout"]
        )
        sys.exit(0 if failed_count == 0 else 1)

    # Validate newspaper argument
    if not args.newspaper:
        parser.error(
            "Newspaper name is required (or use --list-scrapers to see options)"
        )

    # Run the scraper
    print("🌊 Pacific Observatory - Text Scraping Tools")
    print("=" * 50)

    try:
        success, results = asyncio.run(
            run_scraper_by_name(
                newspaper_name=args.newspaper,
                country=args.country,
                mode=mode,
                configs_dir=get_default_configs_dir(),
                project_root=project_root,
                storage_dir=args.storage_dir,
                no_save=args.no_save,
            )
        )

        # Print log file location if scraping was successful
        if success and results:
            print("\n" + "=" * 50)
            country = results.get("country", "unknown")
            newspaper = results.get("newspaper", "unknown")
            # Normalize newspaper name: lowercase and replace spaces with underscores
            normalized_newspaper = newspaper.lower().replace(" ", "_")
            print(
                f"📝 Log file saved to: logs/text/{country}/{normalized_newspaper}/YYYYMMDD_HHMMSS.log"
            )

        if not success:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
