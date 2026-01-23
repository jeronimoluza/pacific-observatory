"""
Observability components for text scraping.

Provides metrics tracking, formatting, and validation for scraper runs.
"""

from .metrics import FieldMetrics, ScraperMetrics
# from .formatters import print_run_summary, detect_quality_issues  # TODO: Task 1.3

__all__ = [
    "FieldMetrics",
    "ScraperMetrics",
    # "save_run_manifest",  # TODO: Task 1.4
    # "print_run_summary",  # TODO: Task 1.3
    # "detect_quality_issues",  # TODO: Task 1.3
]
