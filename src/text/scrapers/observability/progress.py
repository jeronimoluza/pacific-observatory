"""
Progress reporting for live status tracking during scraper runs.

Provides atomic progress file writing for scrapers to report their status,
and functions to read progress and detect stale scrapers.

Progress file location: {base_path}/{country}/{newspaper}/progress.json

JSON format:
{
    "phase": "discovering",
    "last_activity": "2026-01-26T10:30:45.123456",
    "urls_found": 12,
    "articles_scraped": 0,
    "articles_failed": 0
}
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .metrics import _sanitize_name

logger = logging.getLogger(__name__)


class ProgressReporter:
    """
    Reports scraper progress to a file for live status monitoring.

    Uses atomic writes (temp file + rename) to avoid corruption from
    concurrent reads during scraper execution.

    Phases: "starting", "discovering", "scraping", "completed", "failed"

    Usage:
        reporter = ProgressReporter("fiji", "fiji_sun")
        reporter.update(phase="discovering", urls_found=10)
        reporter.update(phase="scraping", articles_scraped=5)
        reporter.cleanup()  # Remove progress file when done
    """

    def __init__(
        self,
        country: str,
        newspaper: str,
        base_path: Optional[str] = None,
    ) -> None:
        """
        Initialize a progress reporter.

        Args:
            country: Country code (e.g., "fiji")
            newspaper: Newspaper name (e.g., "fiji_sun")
            base_path: Base directory for progress files. Defaults to "logs/text"
        """
        self.country = _sanitize_name(country)
        self.newspaper = _sanitize_name(newspaper)
        self.base_path = Path(base_path) if base_path else Path("logs/text")

        # Initialize state
        self.phase = "starting"
        self.urls_found = 0
        self.articles_scraped = 0
        self.articles_failed = 0
        self.started_at = datetime.now()

    @property
    def progress_path(self) -> Path:
        """Return the path to the progress file."""
        return self.base_path / self.country / self.newspaper / "progress.json"

    def update(self, **kwargs) -> None:
        """
        Update progress state and write to file atomically.

        Args:
            **kwargs: State fields to update. Valid fields:
                - phase: str ("starting", "discovering", "scraping", "completed", "failed")
                - urls_found: int
                - articles_scraped: int
                - articles_failed: int
        """
        # Update internal state with provided values
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Build progress data
        data = {
            "phase": self.phase,
            "last_activity": datetime.now().isoformat(),
            "urls_found": self.urls_found,
            "articles_scraped": self.articles_scraped,
            "articles_failed": self.articles_failed,
        }

        # Ensure directory exists
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file, then rename
        # This ensures readers never see partial/corrupted JSON
        fd, temp_path = tempfile.mkstemp(
            dir=self.progress_path.parent, suffix=".tmp", prefix="progress_"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            # Atomic rename
            os.replace(temp_path, self.progress_path)
        except Exception as e:
            # Clean up temp file on error
            logger.warning(f"Failed to write progress file: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def cleanup(self) -> None:
        """
        Remove the progress file.

        Called when scraper completes or fails to clean up progress tracking.
        Does not raise an error if file doesn't exist.
        """
        try:
            if self.progress_path.exists():
                self.progress_path.unlink()
        except OSError as e:
            logger.warning(f"Failed to cleanup progress file: {e}")


def read_progress(
    country: str,
    newspaper: str,
    base_path: Optional[str] = None,
) -> Optional[dict]:
    """
    Read progress data for a scraper.

    Args:
        country: Country code (e.g., "fiji")
        newspaper: Newspaper name (e.g., "fiji_sun")
        base_path: Base directory for progress files. Defaults to "logs/text"

    Returns:
        Progress data as dict, or None if no progress file exists.
    """
    base = Path(base_path) if base_path else Path("logs/text")
    sanitized_country = _sanitize_name(country)
    sanitized_newspaper = _sanitize_name(newspaper)
    progress_path = base / sanitized_country / sanitized_newspaper / "progress.json"

    if not progress_path.exists():
        return None

    try:
        with open(progress_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to decode progress JSON for {newspaper}: {e}")
        return None
    except OSError as e:
        logger.warning(f"Failed to read progress file for {newspaper}: {e}")
        return None


def is_scraper_stale(
    country: str,
    newspaper: str,
    stale_threshold_seconds: int = 120,
    base_path: Optional[str] = None,
) -> bool:
    """
    Check if a scraper has become stale (no activity for too long).

    Args:
        country: Country code (e.g., "fiji")
        newspaper: Newspaper name (e.g., "fiji_sun")
        stale_threshold_seconds: Seconds without activity before considered stale.
            Defaults to 120 seconds.
        base_path: Base directory for progress files. Defaults to "logs/text"

    Returns:
        True if scraper is stale, False otherwise.
        Returns False if no progress file exists (scraper may still be starting).
    """
    # Note: read_progress already sanitizes country and newspaper
    data = read_progress(country, newspaper, base_path)

    if data is None:
        # No progress file - scraper might still be starting up
        return False

    try:
        last_activity = datetime.fromisoformat(data["last_activity"])
        elapsed = (datetime.now() - last_activity).total_seconds()
        return elapsed > stale_threshold_seconds
    except (KeyError, ValueError) as e:
        # Invalid or missing timestamp - assume stale
        logger.warning(f"Failed to parse timestamp for {newspaper}: {e}")
        return True
