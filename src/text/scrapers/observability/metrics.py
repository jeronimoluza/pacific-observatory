"""
Metrics tracking for scraper runs.

Provides in-memory aggregation of extraction quality metrics.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


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
        newspaper: Newspaper name
        country: Country code

    Returns:
        Path to saved manifest file
    """
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
