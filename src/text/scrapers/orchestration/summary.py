"""
Pacific Observatory - Run Summary Formatting

This module provides functions to format human-readable run summaries
for scraper orchestration.
"""

from typing import List, Dict


def format_duration(seconds: int) -> str:
    """
    Format duration in a human-readable way.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "45 seconds" or "47 minutes"
    """
    if seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minutes"
    return f"{seconds} seconds"


def format_run_summary(results: List[Dict], total_duration_seconds: int) -> str:
    """
    Format a human-readable run summary from scraper results.

    Args:
        results: List of result dictionaries with keys:
            - newspaper: str
            - country: str
            - status: str ("success", "failed", "timeout", "skipped")
            - duration_seconds: float
            - articles_scraped: int (optional, for successful scrapers)
            - error_msg: str (optional, for failed/timeout cases)
        total_duration_seconds: Total duration of the run in seconds

    Returns:
        Multi-line summary string
    """
    # Count statuses
    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] in ("failed", "timeout")]
    skipped = [r for r in results if r["status"] == "skipped"]

    # Calculate total articles
    total_articles = sum(r.get("articles_scraped", 0) for r in succeeded)

    # Build summary lines
    lines = []
    lines.append("=" * 50)
    lines.append("=== Scrape Complete ===")
    lines.append("")

    # Succeeded section
    if succeeded:
        if total_articles > 0:
            # Format article count with comma separator
            article_str = f"{total_articles:,}"
            lines.append(
                f"Succeeded: {len(succeeded)} newspapers ({article_str} articles)"
            )
        else:
            lines.append(f"Succeeded: {len(succeeded)} newspapers")

    # Failed section
    if failed:
        lines.append(f"Failed:    {len(failed)} newspapers")
        for result in failed:
            newspaper = result["newspaper"]
            error_msg = result.get("error_msg", "Unknown error")
            lines.append(f"  - {newspaper}: {error_msg}")

    # Skipped section
    if skipped:
        lines.append(f"Skipped:   {len(skipped)} newspapers")

    # Duration
    lines.append("")
    lines.append(f"Duration: {format_duration(total_duration_seconds)}")

    # Output location
    lines.append("Output: data/text/")
    lines.append("=" * 50)

    return "\n".join(lines)
