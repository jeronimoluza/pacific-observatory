"""
Observability components for text scraping.

Provides metrics tracking, formatting, and validation for scraper runs.
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

__all__ = [
    "FieldMetrics",
    "ScraperMetrics",
    "save_run_manifest",
    "save_multi_run_manifest",
    "print_run_summary",
    "detect_quality_issues",
    "print_multi_run_summary",
]
