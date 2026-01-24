"""
Metrics tracking for scraper runs.

Provides in-memory aggregation of extraction quality metrics.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    """
    Sanitize a name for use in filesystem paths.

    Matches CSVStorage._sanitize_name() to ensure consistency.

    Args:
        name: Name to sanitize

    Returns:
        Sanitized name safe for filesystem use
    """
    # Replace spaces with underscores and remove special characters
    sanitized = re.sub(r"[^\w\-_.]", "_", name.replace(" ", "_").lower())
    return sanitized.strip("_")


@dataclass
class FieldMetrics:
    """
    Metrics for a single field extraction (e.g., 'date', 'body').

    Tracks how many times we attempted to extract this field and
    the quality of extracted values.
    """

    total_extracted: int = 0  # How many articles we tried to extract this field from
    successful: int = 0  # Field populated with non-empty value
    empty: int = 0  # Field is None, empty string, or empty list
    invalid: int = 0  # Field failed validation (reserved for future use)

    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_extracted == 0:
            return 0.0
        return (self.successful / self.total_extracted) * 100


@dataclass
class ScraperMetrics:
    """
    Aggregated metrics for a scraper run.

    Tracks article-level counts and field-level extraction quality.
    Updated incrementally during scraping, then formatted at the end.
    """

    newspaper: str
    country: str
    mode: str
    started_at: datetime

    # Article-level counts
    urls_discovered: int = 0
    articles_scraped: int = 0
    articles_failed: int = 0

    # Field-level quality tracking
    field_metrics: Dict[str, FieldMetrics] = field(default_factory=dict)

    # Timing
    duration_seconds: float = 0.0

    def get_field_metric(self, field_name: str) -> FieldMetrics:
        """
        Get or create a FieldMetrics instance for a specific field.

        Args:
            field_name: Name of the field (e.g., 'date', 'body', 'title')

        Returns:
            FieldMetrics instance for this field
        """
        if field_name not in self.field_metrics:
            self.field_metrics[field_name] = FieldMetrics()
        return self.field_metrics[field_name]

    @classmethod
    def from_dict(cls, data: dict) -> "ScraperMetrics":
        """
        Load ScraperMetrics from JSON manifest dictionary.

        Args:
            data: Dictionary loaded from JSON manifest

        Returns:
            ScraperMetrics instance
        """
        # Parse datetime
        started_at = datetime.fromisoformat(data["started_at"])

        # Reconstruct field_metrics from nested dicts
        field_metrics = {}
        if "field_quality" in data:
            for field_name, field_data in data["field_quality"].items():
                field_metrics[field_name] = FieldMetrics(**field_data)

        # Build ScraperMetrics
        counts = data.get("counts", {})
        return cls(
            newspaper=data["newspaper"],
            country=data["country"],
            mode=data["mode"],
            started_at=started_at,
            urls_discovered=counts.get("urls_discovered", 0),
            articles_scraped=counts.get("articles_scraped", 0),
            articles_failed=counts.get("articles_failed", 0),
            field_metrics=field_metrics,
            duration_seconds=data.get("duration_seconds", 0.0),
        )


def save_run_manifest(metrics: ScraperMetrics, newspaper: str, country: str) -> Path:
    """
    Save run manifest as JSON to logs directory.

    Args:
        metrics: ScraperMetrics to save
        newspaper: Newspaper name (will be sanitized to match data folder)
        country: Country code (will be sanitized to match data folder)

    Returns:
        Path to saved manifest file
    """
    # Sanitize names to match data folder structure (e.g., "Caixin Global" -> "caixin_global")
    country = _sanitize_name(country)
    newspaper = _sanitize_name(newspaper)

    # Create directory structure
    manifest_dir = Path(f"logs/text/{country}/{newspaper}/individual")
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = metrics.started_at.strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_dir / f"{timestamp}.json"

    # Build manifest dictionary
    manifest = {
        "newspaper": metrics.newspaper,
        "country": metrics.country,
        "mode": metrics.mode,
        "started_at": metrics.started_at.isoformat(),
        "duration_seconds": metrics.duration_seconds,
        "counts": {
            "urls_discovered": metrics.urls_discovered,
            "articles_scraped": metrics.articles_scraped,
            "articles_failed": metrics.articles_failed,
        },
        "field_quality": {
            field_name: asdict(field_metric)
            for field_name, field_metric in metrics.field_metrics.items()
        },
    }

    # Write JSON
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Saved run manifest to {manifest_path}")

    return manifest_path


def save_multi_run_manifest(
    all_metrics: List[ScraperMetrics],
    started_at: datetime,
    completed_at: datetime,
) -> Path:
    """
    Save aggregate manifest for multi-newspaper run.

    Args:
        all_metrics: List of ScraperMetrics from all newspapers
        started_at: When the multi-run started
        completed_at: When the multi-run completed

    Returns:
        Path to saved manifest file
    """
    from .formatters import detect_quality_issues

    # Create directory
    manifest_dir = Path("logs/text/multi_runs")
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    manifest_path = manifest_dir / f"{timestamp}.json"

    # Calculate totals
    total_articles = sum(m.articles_scraped for m in all_metrics)
    total_failed = sum(m.articles_failed for m in all_metrics)

    # Collect quality issues
    quality_issues = []
    for metrics in all_metrics:
        issues = detect_quality_issues(metrics)
        for issue in issues:
            severity = (
                "critical" if "Critical" in issue or "ALL" in issue else "warning"
            )
            quality_issues.append(
                {
                    "newspaper": metrics.newspaper,
                    "country": metrics.country,
                    "severity": severity,
                    "issue": issue,
                }
            )

    # Build manifest paths
    newspaper_manifests = []
    for metrics in all_metrics:
        # Sanitize names to match actual folder structure
        country = _sanitize_name(metrics.country)
        newspaper = _sanitize_name(metrics.newspaper)

        manifest_path_str = (
            f"logs/text/{country}/{newspaper}/individual/"
            f"{metrics.started_at.strftime('%Y%m%d_%H%M%S')}.json"
        )
        newspaper_manifests.append(manifest_path_str)

    # Build manifest
    manifest = {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "newspapers_run": len(all_metrics),
        "total_articles_scraped": total_articles,
        "total_failed": total_failed,
        "quality_issues": quality_issues,
        "newspaper_manifests": newspaper_manifests,
    }

    # Write
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Saved multi-run manifest to {manifest_path}")

    return manifest_path
