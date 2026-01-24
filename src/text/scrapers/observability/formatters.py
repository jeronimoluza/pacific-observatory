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
