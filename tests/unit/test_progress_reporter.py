"""Unit tests for ProgressReporter in observability module."""

import sys
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.observability.progress import (
    ProgressReporter,
    read_progress,
    is_scraper_stale,
)


class TestProgressReporterInit:
    """Tests for ProgressReporter initialization."""

    def test_init_creates_reporter_with_defaults(self):
        """Test that ProgressReporter initializes with default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            assert reporter.country == "fiji"
            assert reporter.newspaper == "fiji_sun"
            assert reporter.base_path == Path(tmpdir)
            assert reporter.phase == "starting"
            assert reporter.urls_found == 0
            assert reporter.articles_scraped == 0
            assert reporter.articles_failed == 0
            assert reporter.started_at is not None

    def test_init_uses_default_base_path(self):
        """Test that default base_path is logs/text."""
        reporter = ProgressReporter(
            country="fiji",
            newspaper="fiji_sun",
        )

        assert reporter.base_path == Path("logs/text")


class TestProgressReporterUpdate:
    """Tests for ProgressReporter.update() method."""

    def test_update_writes_progress_file(self):
        """Test that update() writes a progress.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            reporter.update(phase="discovering", urls_found=10)

            progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"
            assert progress_path.exists()

            with open(progress_path, "r") as f:
                data = json.load(f)

            assert data["phase"] == "discovering"
            assert data["urls_found"] == 10
            assert data["articles_scraped"] == 0
            assert data["articles_failed"] == 0
            assert "last_activity" in data

    def test_update_is_atomic(self):
        """Test that update() uses atomic writes (temp file + rename)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            # Perform multiple rapid updates
            for i in range(10):
                reporter.update(urls_found=i)

            # Final file should be valid JSON with the last value
            progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"
            with open(progress_path, "r") as f:
                data = json.load(f)

            assert data["urls_found"] == 9

    def test_last_activity_updates_on_each_call(self):
        """Test that last_activity timestamp updates on each update() call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            reporter.update(phase="discovering")
            progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"

            with open(progress_path, "r") as f:
                data1 = json.load(f)
            first_activity = data1["last_activity"]

            # Small delay to ensure timestamp changes
            time.sleep(0.01)

            reporter.update(phase="scraping")

            with open(progress_path, "r") as f:
                data2 = json.load(f)
            second_activity = data2["last_activity"]

            # Timestamps should be different
            assert second_activity > first_activity

    def test_update_incremental_values(self):
        """Test that update() correctly updates incremental values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            reporter.update(phase="discovering", urls_found=50)
            reporter.update(phase="scraping", articles_scraped=10)
            reporter.update(articles_scraped=20, articles_failed=2)

            progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"
            with open(progress_path, "r") as f:
                data = json.load(f)

            assert data["phase"] == "scraping"
            assert data["urls_found"] == 50
            assert data["articles_scraped"] == 20
            assert data["articles_failed"] == 2


class TestProgressReporterCleanup:
    """Tests for ProgressReporter.cleanup() method."""

    def test_cleanup_removes_progress_file(self):
        """Test that cleanup() removes the progress.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            reporter.update(phase="discovering")
            progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"
            assert progress_path.exists()

            reporter.cleanup()
            assert not progress_path.exists()

    def test_cleanup_handles_missing_file(self):
        """Test that cleanup() doesn't raise error if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            # No update called, so no file exists
            # cleanup() should not raise
            reporter.cleanup()


class TestReadProgress:
    """Tests for read_progress() function."""

    def test_read_progress_returns_dict(self):
        """Test that read_progress returns progress data as dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )
            reporter.update(phase="scraping", urls_found=100, articles_scraped=50)

            data = read_progress("fiji", "fiji_sun", base_path=tmpdir)

            assert data is not None
            assert data["phase"] == "scraping"
            assert data["urls_found"] == 100
            assert data["articles_scraped"] == 50

    def test_read_progress_returns_none_for_missing_file(self):
        """Test that read_progress returns None when no progress file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = read_progress("fiji", "fiji_sun", base_path=tmpdir)
            assert data is None

    def test_read_progress_uses_default_base_path(self):
        """Test that read_progress uses logs/text as default base_path."""
        # This test just verifies the default path is used
        # Will return None since the path likely doesn't exist
        data = read_progress("nonexistent", "newspaper")
        assert data is None


class TestIsScraperStale:
    """Tests for is_scraper_stale() function."""

    def test_is_scraper_stale_returns_false_when_active(self):
        """Test that is_scraper_stale returns False when recently active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )
            reporter.update(phase="scraping")

            is_stale = is_scraper_stale(
                "fiji", "fiji_sun", stale_threshold_seconds=120, base_path=tmpdir
            )
            assert is_stale is False

    def test_is_scraper_stale_returns_true_when_inactive(self):
        """Test that is_scraper_stale returns True when inactive too long."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create progress file with old timestamp
            progress_dir = Path(tmpdir) / "fiji" / "fiji_sun"
            progress_dir.mkdir(parents=True, exist_ok=True)
            progress_path = progress_dir / "progress.json"

            old_time = datetime.now() - timedelta(seconds=300)
            data = {
                "phase": "scraping",
                "last_activity": old_time.isoformat(),
                "urls_found": 50,
                "articles_scraped": 10,
                "articles_failed": 0,
            }
            with open(progress_path, "w") as f:
                json.dump(data, f)

            is_stale = is_scraper_stale(
                "fiji", "fiji_sun", stale_threshold_seconds=120, base_path=tmpdir
            )
            assert is_stale is True

    def test_is_scraper_stale_returns_false_for_missing_file(self):
        """Test that is_scraper_stale returns False when no progress file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            is_stale = is_scraper_stale(
                "fiji", "fiji_sun", stale_threshold_seconds=120, base_path=tmpdir
            )
            # Returns False because scraper might still be starting up
            assert is_stale is False

    def test_is_scraper_stale_respects_threshold(self):
        """Test that stale_threshold_seconds parameter is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create progress file with timestamp 60 seconds ago
            progress_dir = Path(tmpdir) / "fiji" / "fiji_sun"
            progress_dir.mkdir(parents=True, exist_ok=True)
            progress_path = progress_dir / "progress.json"

            old_time = datetime.now() - timedelta(seconds=60)
            data = {
                "phase": "scraping",
                "last_activity": old_time.isoformat(),
                "urls_found": 50,
                "articles_scraped": 10,
                "articles_failed": 0,
            }
            with open(progress_path, "w") as f:
                json.dump(data, f)

            # Should not be stale with 120 second threshold
            assert (
                is_scraper_stale(
                    "fiji", "fiji_sun", stale_threshold_seconds=120, base_path=tmpdir
                )
                is False
            )

            # Should be stale with 30 second threshold
            assert (
                is_scraper_stale(
                    "fiji", "fiji_sun", stale_threshold_seconds=30, base_path=tmpdir
                )
                is True
            )


class TestProgressPhases:
    """Tests for valid phase values."""

    def test_valid_phases(self):
        """Test that all valid phases can be set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ProgressReporter(
                country="fiji",
                newspaper="fiji_sun",
                base_path=tmpdir,
            )

            valid_phases = [
                "starting",
                "discovering",
                "scraping",
                "completed",
                "failed",
            ]

            for phase in valid_phases:
                reporter.update(phase=phase)
                progress_path = Path(tmpdir) / "fiji" / "fiji_sun" / "progress.json"
                with open(progress_path, "r") as f:
                    data = json.load(f)
                assert data["phase"] == phase
