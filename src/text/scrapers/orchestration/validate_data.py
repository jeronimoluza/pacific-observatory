"""
Post-run data validation CLI.

Validates CSV output quality and optionally deduplicates entries.
"""

import argparse
import sys
from pathlib import Path

# Set up Python path for imports - must happen before text.* imports
if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    scrapers_dir = script_dir.parent
    text_dir = scrapers_dir.parent
    src_dir = text_dir.parent

    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

from text.scrapers.orchestration.discovery import discover_configs


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate text scraping CSV output quality"
    )
    parser.add_argument(
        "newspaper",
        nargs="?",
        help="Newspaper name to validate (omit for --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all newspapers",
    )
    parser.add_argument(
        "--deduplicate",
        action="store_true",
        help="Remove duplicate URLs (keeps oldest entry with complete fields)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create backup before deduplication (default: True)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.newspaper and not args.all:
        parser.error("Must specify either a newspaper name or --all")

    if args.newspaper and args.all:
        parser.error("Cannot specify both newspaper name and --all")

    print("🔍 Text Data Validator\n")

    if args.all:
        # Discover all configs
        configs_dir = Path("src/text/scrapers/configs")
        configs = discover_configs(configs_dir)

        if not configs:
            print("❌ No configurations found.")
            return 1

        print(f"Validating {len(configs)} newspapers...\n")

        # TODO: Validate each newspaper
        for config in configs:
            newspaper = config["newspaper"]
            country = config["country"]
            print(f"📊 {newspaper} ({country})")
            print("   TODO: Implement validation")
            print()

    else:
        # Validate single newspaper
        newspaper = args.newspaper
        print(f"Validating {newspaper}...\n")
        print("   TODO: Implement validation")

    if args.deduplicate:
        print("\n🧹 Deduplication:")
        print("   TODO: Implement deduplication")

    return 0


if __name__ == "__main__":
    sys.exit(main())
