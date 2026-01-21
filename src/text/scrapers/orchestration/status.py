"""
CLI dashboard for scraper status monitoring.

Provides commands to view recent runs, failures, and statistics.

Usage:
    # Show recent runs (last 24 hours)
    python -m text.scrapers.orchestration.status

    # Show last 24 hours with details
    python -m text.scrapers.orchestration.status --last-24h

    # Show only failures
    python -m text.scrapers.orchestration.status --failures

    # Filter by newspaper
    python -m text.scrapers.orchestration.status --newspaper fiji_sun

    # Show statistics
    python -m text.scrapers.orchestration.status --stats

    # Verbose output with article-level details
    python -m text.scrapers.orchestration.status --verbose
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from text.core.run_tracker import RunTracker, ScraperRun


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        return f"{seconds/3600:.1f}h"


def format_time_ago(dt: datetime) -> str:
    """Format datetime as time ago."""
    now = datetime.utcnow()
    diff = now - dt

    if diff < timedelta(minutes=1):
        return "just now"
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = diff.days
        return f"{days}d ago"


def status_symbol(status: str) -> str:
    """Get a symbol for the status."""
    symbols = {
        "success": "+",
        "failed": "X",
        "running": "~",
        "partial": "!",
    }
    return symbols.get(status, "?")


def print_runs_table(runs: List[ScraperRun], title: str) -> None:
    """Print a table of runs."""
    if not runs:
        print(f"\n{title}")
        print("  No runs found.")
        return

    # Calculate column widths
    max_newspaper = max(len(r.newspaper) for r in runs)
    max_country = max(len(r.country) for r in runs)

    # Header
    print(f"\n=== {title} ===\n")
    header = (
        f"{'Newspaper':<{max_newspaper}} | "
        f"{'Country':<{max_country}} | "
        f"{'Last Run':<10} | "
        f"{'Status':<8} | "
        f"{'Articles':<15} | "
        f"{'Mode':<8}"
    )
    print(header)
    print("-" * len(header))

    # Rows
    for run in runs:
        time_ago = format_time_ago(run.started_at)
        status_str = f"[{status_symbol(run.status)}] {run.status}"

        if run.articles_scraped > 0 or run.articles_failed > 0:
            articles = f"{run.articles_scraped} ok"
            if run.articles_failed > 0:
                articles += f", {run.articles_failed} fail"
        else:
            articles = "-"

        row = (
            f"{run.newspaper:<{max_newspaper}} | "
            f"{run.country:<{max_country}} | "
            f"{time_ago:<10} | "
            f"{status_str:<8} | "
            f"{articles:<15} | "
            f"{run.mode:<8}"
        )
        print(row)

    # Summary
    success = sum(1 for r in runs if r.status == "success")
    failed = sum(1 for r in runs if r.status == "failed")
    running = sum(1 for r in runs if r.status == "running")

    print()
    print(f"Summary: {success} SUCCESS, {failed} FAILED, {running} RUNNING")


def print_failures_detail(runs: List[ScraperRun]) -> None:
    """Print detailed information about failures."""
    if not runs:
        print("\n=== Failures (Last 7 Days) ===")
        print("  No failures found.")
        return

    print("\n=== Failures (Last 7 Days) ===\n")

    for run in runs:
        duration = ""
        if run.completed_at:
            secs = (run.completed_at - run.started_at).total_seconds()
            duration = f" ({format_duration(secs)})"

        print(f"[{status_symbol(run.status)}] {run.newspaper} ({run.country})")
        print(f"    Run ID:  {run.run_id[:8]}")
        print(f"    Started: {run.started_at.strftime('%Y-%m-%d %H:%M:%S')}{duration}")
        print(f"    Mode:    {run.mode}")
        if run.error_message:
            # Truncate long error messages
            msg = run.error_message[:100]
            if len(run.error_message) > 100:
                msg += "..."
            print(f"    Error:   {msg}")
        print()


def print_stats(tracker: RunTracker, days: int = 30) -> None:
    """Print aggregate statistics."""
    stats = tracker.get_newspaper_stats(days=days)

    if not stats:
        print(f"\n=== Statistics (Last {days} Days) ===")
        print("  No data available.")
        return

    # Calculate column widths
    max_newspaper = max(len(s["newspaper"]) for s in stats)
    max_country = max(len(s["country"]) for s in stats)

    print(f"\n=== Statistics (Last {days} Days) ===\n")

    header = (
        f"{'Newspaper':<{max_newspaper}} | "
        f"{'Country':<{max_country}} | "
        f"{'Runs':<5} | "
        f"{'Success':<7} | "
        f"{'Failed':<6} | "
        f"{'Rate':<6} | "
        f"{'Articles':<10} | "
        f"{'Last Run':<12}"
    )
    print(header)
    print("-" * len(header))

    for stat in stats:
        total = stat["total_runs"]
        success = stat["success_count"]
        failed = stat["failure_count"]
        rate = f"{100*success/total:.0f}%" if total > 0 else "-"
        articles = str(stat["total_articles"] or 0)

        last_run = stat["last_run"]
        if last_run:
            last_dt = datetime.fromisoformat(last_run)
            last_str = format_time_ago(last_dt)
        else:
            last_str = "-"

        row = (
            f"{stat['newspaper']:<{max_newspaper}} | "
            f"{stat['country']:<{max_country}} | "
            f"{total:<5} | "
            f"{success:<7} | "
            f"{failed:<6} | "
            f"{rate:<6} | "
            f"{articles:<10} | "
            f"{last_str:<12}"
        )
        print(row)

    # Overall summary
    total_runs = sum(s["total_runs"] for s in stats)
    total_success = sum(s["success_count"] for s in stats)
    total_failed = sum(s["failure_count"] for s in stats)
    total_articles = sum(s["total_articles"] or 0 for s in stats)
    overall_rate = f"{100*total_success/total_runs:.0f}%" if total_runs > 0 else "-"

    print()
    print(
        f"Total: {total_runs} runs, {total_success} success, {total_failed} failed ({overall_rate})"
    )
    print(f"       {total_articles} articles scraped")


def main():
    """Main entry point for the status CLI."""
    parser = argparse.ArgumentParser(
        description="View scraper run status and statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Show runs from last 24 hours
  %(prog)s --failures               # Show failed runs
  %(prog)s --newspaper fiji_sun     # Filter by newspaper
  %(prog)s --stats                  # Show aggregate statistics
  %(prog)s --stats --days 7         # Stats for last 7 days
        """,
    )

    parser.add_argument(
        "--last-24h",
        action="store_true",
        help="Show runs from the last 24 hours (default)",
    )

    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of hours to look back (default: 24)",
    )

    parser.add_argument(
        "--failures",
        action="store_true",
        help="Show only failed runs",
    )

    parser.add_argument(
        "--newspaper",
        type=str,
        help="Filter by newspaper name",
    )

    parser.add_argument(
        "--country",
        type=str,
        help="Filter by country",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show aggregate statistics instead of run list",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to include in statistics (default: 30)",
    )

    parser.add_argument(
        "--db",
        type=str,
        help="Path to the SQLite database (default: data/text/scraper_runs.db)",
    )

    args = parser.parse_args()

    # Initialize tracker
    db_path = Path(args.db) if args.db else None
    tracker = RunTracker(db_path=db_path)

    # Dispatch to appropriate view
    if args.stats:
        print_stats(tracker, days=args.days)
    elif args.failures:
        failures = tracker.get_failures(
            days=7,
            newspaper=args.newspaper,
        )
        print_failures_detail(failures)
    else:
        runs = tracker.get_recent_runs(
            hours=args.hours,
            newspaper=args.newspaper,
            country=args.country,
        )
        title = f"Scraper Status (Last {args.hours} Hours)"
        if args.newspaper:
            title += f" - {args.newspaper}"
        if args.country:
            title += f" - {args.country}"
        print_runs_table(runs, title)


if __name__ == "__main__":
    main()
