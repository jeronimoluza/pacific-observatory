"""
Formatting utilities for displaying scraper metrics.

Provides console output formatting and quality issue detection.
"""

import logging
from typing import List
from .metrics import ScraperMetrics

logger = logging.getLogger(__name__)


def detect_quality_issues(metrics: ScraperMetrics) -> List[str]:
    """
    Detect data quality issues from metrics.

    Analyzes field-level extraction quality and flags critical issues
    like missing required fields or high failure rates.

    Args:
        metrics: ScraperMetrics to analyze

    Returns:
        List of warning strings describing quality issues
    """
    warnings = []

    # Required fields that should have high success rates
    required_fields = ["url", "title", "date", "body"]

    for field_name in required_fields:
        if field_name not in metrics.field_metrics:
            continue

        field_metric = metrics.field_metrics[field_name]

        # Skip if no data
        if field_metric.total_extracted == 0:
            continue

        # Calculate empty percentage
        empty_pct = (field_metric.empty / field_metric.total_extracted) * 100

        # Critical: >50% empty for required fields
        if empty_pct > 50:
            if empty_pct == 100:
                warnings.append(
                    f"Critical: ALL articles missing '{field_name}' field - check cleaning config"
                )
            else:
                warnings.append(
                    f"Critical: {empty_pct:.0f}% of articles missing '{field_name}' field"
                )
        # Warning: 20-50% empty
        elif empty_pct > 20:
            if field_name == "body":
                warnings.append(
                    f"{empty_pct:.0f}% of articles have empty body (likely dead URLs)"
                )
            else:
                warnings.append(
                    f"Warning: {empty_pct:.0f}% of articles missing '{field_name}' field"
                )

    return warnings


def print_run_summary(metrics: ScraperMetrics) -> None:
    """
    Print formatted run summary to console.

    Displays article counts, field quality metrics, and warnings.

    Args:
        metrics: ScraperMetrics to format and display
    """
    print(f"\n=== Scrape Complete: {metrics.newspaper} ===\n")

    # Article counts
    print("Articles:")
    print(f"  Discovered: {metrics.urls_discovered} URLs")
    print(f"  Scraped:    {metrics.articles_scraped} articles")
    if metrics.articles_failed > 0:
        fail_pct = (
            metrics.articles_failed
            / (metrics.articles_scraped + metrics.articles_failed)
        ) * 100
        print(f"  Failed:     {metrics.articles_failed} articles ({fail_pct:.0f}%)")

    # Duration
    if metrics.duration_seconds > 0:
        minutes = int(metrics.duration_seconds / 60)
        seconds = int(metrics.duration_seconds % 60)
        if minutes > 0:
            print(f"\nDuration: {minutes}m {seconds}s")
        else:
            print(f"\nDuration: {seconds}s")

    # Field quality
    if metrics.field_metrics:
        print("\nField Quality:")
        # Sort fields for consistent output
        for field_name in sorted(metrics.field_metrics.keys()):
            field_metric = metrics.field_metrics[field_name]

            if field_metric.total_extracted == 0:
                continue

            success_pct = field_metric.success_rate()
            status = "✓" if success_pct > 90 else "✗"

            print(
                f"  {field_name}: {field_metric.successful}/{field_metric.total_extracted} "
                f"{status} ({success_pct:.0f}%)"
            )

            if field_metric.empty > 0:
                print(f"    └─ {field_metric.empty} empty")

    # Quality warnings
    warnings = detect_quality_issues(metrics)
    if warnings:
        print("\n⚠️  QUALITY ISSUES DETECTED:")
        for warning in warnings:
            print(f"  • {warning}")

    print()  # Blank line at end


def print_multi_run_summary(all_metrics: List[ScraperMetrics]) -> None:
    """
    Print aggregate summary for multiple scraper runs.

    Args:
        all_metrics: List of ScraperMetrics from multiple newspapers
    """
    if not all_metrics:
        print("\n=== Multi-Scraper Run Complete ===")
        print("No results collected.")
        return

    print("\n=== Multi-Scraper Run Complete ===\n")

    # Calculate totals
    total_newspapers = len(all_metrics)
    total_articles = sum(m.articles_scraped for m in all_metrics)
    total_failed = sum(m.articles_failed for m in all_metrics)
    total_duration = sum(m.duration_seconds for m in all_metrics)

    # Calculate success rate
    total_attempted = total_articles + total_failed
    if total_attempted > 0:
        success_rate = (total_articles / total_attempted) * 100
    else:
        success_rate = 0

    print(f"Total newspapers: {total_newspapers}")

    # Duration
    hours = int(total_duration / 3600)
    minutes = int((total_duration % 3600) / 60)
    if hours > 0:
        print(f"Total duration: {hours}h {minutes}m")
    else:
        print(f"Total duration: {minutes}m")

    print("\nOverall:")
    print(f"  Articles scraped: {total_articles:,}")
    if total_failed > 0:
        print(f"  Articles failed:  {total_failed}")
        print(f"  Success rate: {success_rate:.1f}%")

    # Collect quality issues by severity
    critical_issues = []
    warnings = []

    for metrics in all_metrics:
        issues = detect_quality_issues(metrics)
        if issues:
            for issue in issues:
                if "Critical" in issue or "ALL articles" in issue:
                    critical_issues.append((metrics.newspaper, metrics.country, issue))
                else:
                    warnings.append((metrics.newspaper, metrics.country, issue))

    # Print quality issues
    if critical_issues or warnings:
        total_issues = len(critical_issues) + len(warnings)
        print(f"\nQuality Issues Found: {total_issues} newspapers\n")

        for newspaper, country, issue in critical_issues:
            print(f"  ✗ {newspaper} ({country})")
            print(f"    • {issue}\n")

        for newspaper, country, issue in warnings:
            print(f"  ⚠ {newspaper} ({country})")
            print(f"    • {issue}\n")

    print()
