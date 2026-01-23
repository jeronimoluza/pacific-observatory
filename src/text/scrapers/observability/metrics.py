"""
Metrics tracking for scraper runs.

Provides in-memory aggregation of extraction quality metrics.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

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
    Aggregate metrics for a scraper run.

    Tracks overall extraction quality across all articles and fields.
    """

    newspaper_id: str
    run_start: datetime
    run_end: Optional[datetime] = None

    # Discovery metrics
    urls_discovered: int = 0
    urls_already_scraped: int = 0
    urls_pending: int = 0

    # Extraction metrics
    articles_attempted: int = 0
    articles_extracted: int = 0
    articles_failed: int = 0

    # Field-level metrics
    field_metrics: Dict[str, FieldMetrics] = field(default_factory=dict)

    # Error tracking
    errors: list = field(default_factory=list)

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

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to a JSON-serializable dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data["run_start"] = self.run_start.isoformat()
        if self.run_end:
            data["run_end"] = self.run_end.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScraperMetrics":
        """
        Create ScraperMetrics instance from a dictionary.

        Args:
            data: Dictionary containing metrics data

        Returns:
            ScraperMetrics instance
        """
        # Convert ISO format strings back to datetime objects
        data = data.copy()  # Don't modify original
        data["run_start"] = datetime.fromisoformat(data["run_start"])
        if data.get("run_end"):
            data["run_end"] = datetime.fromisoformat(data["run_end"])

        # Convert field_metrics dict back to FieldMetrics instances
        if "field_metrics" in data:
            field_metrics = {}
            for field_name, field_data in data["field_metrics"].items():
                field_metrics[field_name] = FieldMetrics(**field_data)
            data["field_metrics"] = field_metrics

        return cls(**data)

    def save(self, output_path: Path) -> None:
        """
        Save metrics to a JSON file.

        Args:
            output_path: Path to save the metrics JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved metrics to {output_path}")

    @classmethod
    def load(cls, input_path: Path) -> "ScraperMetrics":
        """
        Load metrics from a JSON file.

        Args:
            input_path: Path to the metrics JSON file

        Returns:
            ScraperMetrics instance
        """
        with open(input_path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)
