"""
Checkpoint/resume system for resilient scraping.

Saves scraping progress to disk so that interrupted runs can be resumed.
This is particularly useful for long-running scrapes that may be interrupted
by network issues, rate limiting, or system restarts.

Usage:
    from text.core.checkpoints import CheckpointManager, ScrapeCheckpoint

    manager = CheckpointManager()

    # Start a new run
    checkpoint = manager.create(
        run_id="abc123",
        newspaper="fiji_sun",
        discovered_urls=["url1", "url2", "url3"],
    )

    # Save progress
    checkpoint.mark_scraped("url1")
    manager.save(checkpoint)

    # Resume later
    checkpoint = manager.load("abc123")
    pending = manager.get_pending_urls(checkpoint)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from .logging_config import get_logger
from .errors import CheckpointError

logger = get_logger(__name__)


@dataclass
class ScrapeCheckpoint:
    """
    Represents the state of a scraping run.

    Tracks which URLs have been discovered, scraped, or failed,
    allowing runs to be resumed from where they left off.
    """

    run_id: str
    newspaper: str
    country: str
    mode: str
    discovered_urls: List[str] = field(default_factory=list)
    scraped_urls: Set[str] = field(default_factory=set)
    failed_urls: Set[str] = field(default_factory=set)
    skipped_urls: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    config_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_scraped(self, url: str) -> None:
        """Mark a URL as successfully scraped."""
        self.scraped_urls.add(url)
        self.last_updated = datetime.utcnow()

    def mark_failed(self, url: str, error: Optional[str] = None) -> None:
        """Mark a URL as failed."""
        self.failed_urls.add(url)
        self.last_updated = datetime.utcnow()
        if error:
            if "errors" not in self.metadata:
                self.metadata["errors"] = {}
            self.metadata["errors"][url] = error

    def mark_skipped(self, url: str, reason: Optional[str] = None) -> None:
        """Mark a URL as skipped (e.g., already exists)."""
        self.skipped_urls.add(url)
        self.last_updated = datetime.utcnow()

    def add_discovered_urls(self, urls: List[str]) -> int:
        """Add newly discovered URLs, returns count of new URLs."""
        existing = set(self.discovered_urls)
        new_urls = [u for u in urls if u not in existing]
        self.discovered_urls.extend(new_urls)
        self.last_updated = datetime.utcnow()
        return len(new_urls)

    @property
    def pending_urls(self) -> List[str]:
        """Get URLs that haven't been processed yet."""
        processed = self.scraped_urls | self.failed_urls | self.skipped_urls
        return [u for u in self.discovered_urls if u not in processed]

    @property
    def progress_percent(self) -> float:
        """Get completion percentage."""
        total = len(self.discovered_urls)
        if total == 0:
            return 0.0
        processed = (
            len(self.scraped_urls) + len(self.failed_urls) + len(self.skipped_urls)
        )
        return 100.0 * processed / total

    @property
    def is_complete(self) -> bool:
        """Check if all discovered URLs have been processed."""
        return len(self.pending_urls) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "newspaper": self.newspaper,
            "country": self.country,
            "mode": self.mode,
            "discovered_urls": self.discovered_urls,
            "scraped_urls": list(self.scraped_urls),
            "failed_urls": list(self.failed_urls),
            "skipped_urls": list(self.skipped_urls),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "config_hash": self.config_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapeCheckpoint":
        """Create from dictionary."""
        return cls(
            run_id=data["run_id"],
            newspaper=data["newspaper"],
            country=data["country"],
            mode=data["mode"],
            discovered_urls=data.get("discovered_urls", []),
            scraped_urls=set(data.get("scraped_urls", [])),
            failed_urls=set(data.get("failed_urls", [])),
            skipped_urls=set(data.get("skipped_urls", [])),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            config_hash=data.get("config_hash"),
            metadata=data.get("metadata", {}),
        )


class CheckpointManager:
    """
    Manages saving and loading of checkpoints.

    Checkpoints are saved as JSON files in a dedicated directory.
    """

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        """
        Initialize the checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoints.
                           Defaults to data/text/checkpoints/
        """
        if checkpoint_dir is None:
            checkpoint_dir = Path("data/text/checkpoints")

        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, run_id: str) -> Path:
        """Get the file path for a checkpoint."""
        return self.checkpoint_dir / f"{run_id}.json"

    def create(
        self,
        run_id: str,
        newspaper: str,
        country: str,
        mode: str = "full",
        discovered_urls: Optional[List[str]] = None,
        config_hash: Optional[str] = None,
    ) -> ScrapeCheckpoint:
        """
        Create a new checkpoint.

        Args:
            run_id: Unique identifier for the run
            newspaper: Newspaper being scraped
            country: Country of the newspaper
            mode: Scrape mode (full, update, etc.)
            discovered_urls: Initial list of URLs to scrape
            config_hash: Hash of the config file

        Returns:
            New ScrapeCheckpoint instance
        """
        checkpoint = ScrapeCheckpoint(
            run_id=run_id,
            newspaper=newspaper,
            country=country,
            mode=mode,
            discovered_urls=discovered_urls or [],
            config_hash=config_hash,
        )
        logger.info(f"Created checkpoint for run {run_id}")
        return checkpoint

    def save(self, checkpoint: ScrapeCheckpoint) -> None:
        """
        Save a checkpoint to disk.

        Args:
            checkpoint: The checkpoint to save

        Raises:
            CheckpointError: If save fails
        """
        try:
            path = self._get_checkpoint_path(checkpoint.run_id)
            # Write to temp file first, then rename (atomic operation)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(checkpoint.to_dict(), indent=2))
            temp_path.rename(path)
            logger.debug(f"Saved checkpoint {checkpoint.run_id}")
        except Exception as e:
            raise CheckpointError(
                f"Failed to save checkpoint: {e}",
                run_id=checkpoint.run_id,
            ) from e

    def load(self, run_id: str) -> Optional[ScrapeCheckpoint]:
        """
        Load a checkpoint from disk.

        Args:
            run_id: The run ID to load

        Returns:
            ScrapeCheckpoint if found, None otherwise

        Raises:
            CheckpointError: If load fails (not for missing files)
        """
        path = self._get_checkpoint_path(run_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            checkpoint = ScrapeCheckpoint.from_dict(data)
            logger.info(f"Loaded checkpoint {run_id}")
            return checkpoint
        except Exception as e:
            raise CheckpointError(
                f"Failed to load checkpoint: {e}",
                run_id=run_id,
            ) from e

    def delete(self, run_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            run_id: The run ID to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._get_checkpoint_path(run_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted checkpoint {run_id}")
            return True
        return False

    def exists(self, run_id: str) -> bool:
        """Check if a checkpoint exists."""
        return self._get_checkpoint_path(run_id).exists()

    def get_pending_urls(self, checkpoint: ScrapeCheckpoint) -> List[str]:
        """
        Get URLs that still need to be processed.

        Args:
            checkpoint: The checkpoint to query

        Returns:
            List of pending URLs
        """
        return checkpoint.pending_urls

    def list_checkpoints(
        self,
        newspaper: Optional[str] = None,
        include_complete: bool = False,
    ) -> List[ScrapeCheckpoint]:
        """
        List all checkpoints.

        Args:
            newspaper: Filter by newspaper (optional)
            include_complete: Include completed checkpoints

        Returns:
            List of ScrapeCheckpoint objects
        """
        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoint = ScrapeCheckpoint.from_dict(data)

                # Apply filters
                if newspaper and checkpoint.newspaper != newspaper:
                    continue
                if not include_complete and checkpoint.is_complete:
                    continue

                checkpoints.append(checkpoint)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {path}: {e}")

        return sorted(checkpoints, key=lambda c: c.last_updated, reverse=True)

    def get_resumable(self, newspaper: str) -> Optional[ScrapeCheckpoint]:
        """
        Get the most recent incomplete checkpoint for a newspaper.

        Args:
            newspaper: Newspaper to find checkpoint for

        Returns:
            Most recent incomplete checkpoint, or None
        """
        checkpoints = self.list_checkpoints(newspaper=newspaper, include_complete=False)
        return checkpoints[0] if checkpoints else None

    def cleanup_old(self, days: int = 7) -> int:
        """
        Delete checkpoints older than N days.

        Args:
            days: Age threshold in days

        Returns:
            Number of checkpoints deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = 0

        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                last_updated = datetime.fromisoformat(data["last_updated"])
                if last_updated < cutoff:
                    path.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to check checkpoint {path}: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old checkpoints")

        return deleted

    def cleanup_complete(self) -> int:
        """
        Delete all completed checkpoints.

        Returns:
            Number of checkpoints deleted
        """
        deleted = 0

        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoint = ScrapeCheckpoint.from_dict(data)
                if checkpoint.is_complete:
                    path.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to check checkpoint {path}: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} completed checkpoints")

        return deleted


# Global manager instance
_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get the global checkpoint manager."""
    global _manager
    if _manager is None:
        _manager = CheckpointManager()
    return _manager
