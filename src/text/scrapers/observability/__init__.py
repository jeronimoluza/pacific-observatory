"""
Observability components for text scraping.

Provides metrics tracking, formatting, progress reporting, and validation
for scraper runs.
"""

from .metrics import (
    FieldMetrics,
    ScraperMetrics,
    save_run_manifest,
    save_multi_run_manifest,
)
from .formatters import (
    print_run_summary,
    detect_quality_issues,
    print_multi_run_summary,
)
from .progress import (
    ProgressReporter,
    read_progress,
    is_scraper_stale,
)

__all__ = [
    # Metrics
    "FieldMetrics",
    "ScraperMetrics",
    "save_run_manifest",
    "save_multi_run_manifest",
    # Formatters
    "print_run_summary",
    "detect_quality_issues",
    "print_multi_run_summary",
    # Progress reporting
    "ProgressReporter",
    "read_progress",
    "is_scraper_stale",
]
