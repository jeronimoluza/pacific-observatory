"""
CLI for checking the text database overview.

Provides a summary table of all scraped news sources including
article counts, failed scrapes, and pending URLs.

Usage:
    python -m text.scrapers.orchestration.check_database

    # Specify a custom data folder
    python -m text.scrapers.orchestration.check_database --data-path /path/to/data
"""

import argparse
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd


def get_data_folder() -> Path:
    """Get the data folder path from environment or default."""
    env_path = os.environ.get("DATA_FOLDER_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).parent.parent.parent.parent.parent / "data" / "text"


def read_csv_info(path: Path) -> Dict:
    """
    Read CSV file and extract all relevant info in one pass.

    Returns:
        Dict with keys: status, count, latest_date, updated_at, urls
        - status: "yes" (readable), "no" (missing), "error" (parse error)
    """
    if not path.exists():
        return {
            "status": "no",
            "count": 0,
            "latest_date": None,
            "updated_at": None,
            "urls": set(),
        }

    try:
        df = pd.read_csv(path)
        result = {
            "status": "yes",
            "count": len(df),
            "latest_date": None,
            "updated_at": None,
            "urls": set(),
        }

        # Extract latest date
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"], errors="coerce")
            max_date = dates.max()
            if pd.notna(max_date):
                result["latest_date"] = max_date.strftime("%Y-%m-%d")

        # Extract updated_at
        if "_scraped_at" in df.columns:
            timestamps = pd.to_datetime(df["_scraped_at"], errors="coerce")
            max_ts = timestamps.max()
            if pd.notna(max_ts):
                result["updated_at"] = max_ts.strftime("%Y-%m-%d %H:%M")

        # Extract URLs
        if "url" in df.columns:
            result["urls"] = set(df["url"].dropna().astype(str))

        return result
    except Exception:
        return {
            "status": "error",
            "count": 0,
            "latest_date": None,
            "updated_at": None,
            "urls": set(),
        }


def count_failed_news(failed_dir: Path) -> int:
    """Count total rows in all failed_news_*.csv files."""
    if not failed_dir.exists():
        return 0
    total = 0
    for f in failed_dir.glob("failed_news_*.csv"):
        try:
            df = pd.read_csv(f)
            total += len(df)
        except Exception:
            continue
    return total


def get_failed_urls(failed_dir: Path) -> set:
    """Get all URLs from failed_urls_*.csv files."""
    if not failed_dir.exists():
        return set()
    urls = set()
    for f in failed_dir.glob("failed_urls_*.csv"):
        try:
            df = pd.read_csv(f)
            if "url" in df.columns:
                urls.update(df["url"].dropna().astype(str))
        except Exception:
            continue
    return urls


def collect_source_info(data_folder: Path) -> List[Dict]:
    """Collect information about all sources in the data folder."""
    sources = []

    if not data_folder.exists():
        return sources

    # Iterate through country directories
    for country_dir in sorted(data_folder.iterdir()):
        if not country_dir.is_dir():
            continue
        country = country_dir.name

        # Iterate through source directories
        for source_dir in sorted(country_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            source = source_dir.name

            news_csv = source_dir / "news.csv"
            urls_csv = source_dir / "urls.csv"
            failed_dir = source_dir / "failed"

            # Read CSV files once and extract all info
            news_info = read_csv_info(news_csv)
            urls_info = read_csv_info(urls_csv)

            # Calculate pending: URLs in (urls.csv + failed_urls) but not in news.csv
            failed_urls = get_failed_urls(failed_dir)
            all_available = urls_info["urls"] | failed_urls
            pending = len(all_available - news_info["urls"])

            info = {
                "country": country,
                "source": source,
                "news_status": news_info["status"],
                "urls_status": urls_info["status"],
                "articles": news_info["count"],
                "failed": count_failed_news(failed_dir),
                "pending": pending,
                "latest_date": news_info["latest_date"],
                "updated_at": news_info["updated_at"],
            }
            sources.append(info)

    return sources


def print_database_table(sources: List[Dict]) -> None:
    """Print the database overview table."""
    if not sources:
        print("\n=== Text Database Overview ===")
        print("  No sources found.")
        return

    # Calculate column widths
    max_country = max(len(s["country"]) for s in sources)
    max_source = max(len(s["source"]) for s in sources)
    max_country = max(max_country, len("Country"))
    max_source = max(max_source, len("Source"))

    # Header
    print("\n=== Text Database Overview ===\n")
    header = (
        f"{'Country':<{max_country}} | "
        f"{'Source':<{max_source}} | "
        f"{'news.csv':<8} | "
        f"{'urls.csv':<8} | "
        f"{'# Articles':>10} | "
        f"{'# Failed':>8} | "
        f"{'# Pending':>9} | "
        f"{'Latest Date':<11} | "
        f"{'Updated At':<16}"
    )
    print(header)
    print("-" * len(header))

    # Rows
    total_articles = 0
    total_failed = 0
    total_pending = 0

    for s in sources:
        news_str = s["news_status"]
        urls_str = s["urls_status"]
        latest = s["latest_date"] or "N/A"
        updated = s["updated_at"] or "N/A"

        row = (
            f"{s['country']:<{max_country}} | "
            f"{s['source']:<{max_source}} | "
            f"{news_str:<8} | "
            f"{urls_str:<8} | "
            f"{s['articles']:>10} | "
            f"{s['failed']:>8} | "
            f"{s['pending']:>9} | "
            f"{latest:<11} | "
            f"{updated:<16}"
        )
        print(row)

        total_articles += s["articles"]
        total_failed += s["failed"]
        total_pending += s["pending"]

    # Total row
    print("-" * len(header))
    total_row = (
        f"{'TOTAL':<{max_country}} | "
        f"{'':<{max_source}} | "
        f"{'':<8} | "
        f"{'':<8} | "
        f"{total_articles:>10} | "
        f"{total_failed:>8} | "
        f"{total_pending:>9} | "
        f"{'':<11} | "
        f"{'':<16}"
    )
    print(total_row)

    # Summary
    print()
    print(f"Total sources: {len(sources)}")
    print(f"Total articles: {total_articles:,}")
    if total_failed > 0:
        print(f"Total failed: {total_failed:,}")
    if total_pending > 0:
        print(f"Total pending: {total_pending:,}")


def main():
    """Main entry point for the database check CLI."""
    parser = argparse.ArgumentParser(
        description="View text database overview for all scraped sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Show database overview
  %(prog)s --data-path ../data/text     # Use custom data path
        """,
    )

    parser.add_argument(
        "--data-path",
        type=str,
        help="Path to the data folder (default: DATA_FOLDER_PATH env or ../data/text)",
    )

    args = parser.parse_args()

    # Get data folder
    if args.data_path:
        data_folder = Path(args.data_path)
    else:
        data_folder = get_data_folder()

    # Collect and display info
    sources = collect_source_info(data_folder)
    print_database_table(sources)


if __name__ == "__main__":
    main()
