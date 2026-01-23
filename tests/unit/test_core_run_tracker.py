"""Unit tests for the run tracking database."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.core.run_tracker import (
    RunTracker,
    ScraperRun,
    compute_config_hash,
)


@pytest.fixture
def tracker():
    """Create a run tracker with a temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    tracker = RunTracker(db_path=db_path)
    yield tracker

    # Cleanup
    if db_path.exists():
        db_path.unlink()


class TestScraperRun:
    """Tests for the ScraperRun dataclass."""

    def test_creates_run_with_defaults(self):
        """ScraperRun should create with default values."""
        run = ScraperRun(
            run_id="abc123",
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
            started_at=datetime.utcnow(),
        )
        assert run.status == "running"
        assert run.articles_found == 0
        assert run.articles_scraped == 0
        assert run.articles_failed == 0
        assert run.completed_at is None
        assert run.error_message is None


class TestRunTracker:
    """Tests for the RunTracker class."""

    def test_start_run_creates_record(self, tracker):
        """start_run should create a run record in the database."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        assert run.run_id is not None
        assert run.newspaper == "fiji_sun"
        assert run.country == "fiji"
        assert run.mode == "update"
        assert run.status == "running"

    def test_start_run_with_config_hash(self, tracker):
        """start_run should store config hash."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="full",
            config_hash="abc123def456",
        )

        assert run.config_hash == "abc123def456"

    def test_get_run_returns_record(self, tracker):
        """get_run should return the correct run record."""
        created = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        retrieved = tracker.get_run(created.run_id)

        assert retrieved is not None
        assert retrieved.run_id == created.run_id
        assert retrieved.newspaper == "fiji_sun"

    def test_get_run_returns_none_for_missing(self, tracker):
        """get_run should return None for non-existent run."""
        result = tracker.get_run("nonexistent")
        assert result is None

    def test_update_run_modifies_counters(self, tracker):
        """update_run should modify article counters."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        tracker.update_run(
            run.run_id,
            articles_found=50,
            articles_scraped=30,
            articles_failed=5,
        )

        updated = tracker.get_run(run.run_id)
        assert updated.articles_found == 50
        assert updated.articles_scraped == 30
        assert updated.articles_failed == 5

    def test_complete_run_sets_status(self, tracker):
        """complete_run should set status and completion time."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        tracker.complete_run(
            run.run_id,
            status="success",
            articles_scraped=45,
        )

        completed = tracker.get_run(run.run_id)
        assert completed.status == "success"
        assert completed.completed_at is not None
        assert completed.articles_scraped == 45

    def test_complete_run_with_error(self, tracker):
        """complete_run should store error message."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        tracker.complete_run(
            run.run_id,
            status="failed",
            error_message="Connection timeout",
        )

        completed = tracker.get_run(run.run_id)
        assert completed.status == "failed"
        assert completed.error_message == "Connection timeout"

    def test_record_article_stores_result(self, tracker):
        """record_article should store article result."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        tracker.record_article(
            run.run_id,
            url="https://example.com/article/1",
            status="success",
        )

        # Query article_results table directly
        with tracker._connect() as conn:
            row = conn.execute(
                "SELECT * FROM article_results WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()

        assert row is not None
        assert row["url"] == "https://example.com/article/1"
        assert row["status"] == "success"

    def test_record_article_with_error(self, tracker):
        """record_article should store error type."""
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )

        tracker.record_article(
            run.run_id,
            url="https://example.com/article/1",
            status="failed",
            error_type="timeout",
        )

        with tracker._connect() as conn:
            row = conn.execute(
                "SELECT * FROM article_results WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()

        assert row["error_type"] == "timeout"

    def test_get_recent_runs_filters_by_time(self, tracker):
        """get_recent_runs should filter by time."""
        # Create runs
        for i in range(3):
            run = tracker.start_run(
                newspaper=f"paper_{i}",
                country="fiji",
                mode="update",
            )
            tracker.complete_run(run.run_id, status="success")

        runs = tracker.get_recent_runs(hours=24)
        assert len(runs) == 3

    def test_get_recent_runs_filters_by_newspaper(self, tracker):
        """get_recent_runs should filter by newspaper."""
        for name in ["fiji_sun", "fiji_times", "khmer_times"]:
            run = tracker.start_run(
                newspaper=name,
                country="fiji" if "fiji" in name else "cambodia",
                mode="update",
            )
            tracker.complete_run(run.run_id, status="success")

        runs = tracker.get_recent_runs(hours=24, newspaper="fiji_sun")
        assert len(runs) == 1
        assert runs[0].newspaper == "fiji_sun"

    def test_get_failures_returns_failed_runs(self, tracker):
        """get_failures should return only failed runs."""
        # Create successful run
        run1 = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )
        tracker.complete_run(run1.run_id, status="success")

        # Create failed run
        run2 = tracker.start_run(
            newspaper="khmer_times",
            country="cambodia",
            mode="update",
        )
        tracker.complete_run(run2.run_id, status="failed", error_message="Error")

        failures = tracker.get_failures(days=7)
        assert len(failures) == 1
        assert failures[0].newspaper == "khmer_times"

    def test_get_last_successful_run(self, tracker):
        """get_last_successful_run should return most recent success."""
        # Create multiple runs
        for i in range(3):
            run = tracker.start_run(
                newspaper="fiji_sun",
                country="fiji",
                mode="update",
            )
            tracker.complete_run(run.run_id, status="success", articles_scraped=i * 10)

        last = tracker.get_last_successful_run("fiji_sun")
        assert last is not None
        assert last.articles_scraped == 20  # Last one had 20

    def test_get_newspaper_stats(self, tracker):
        """get_newspaper_stats should return aggregate stats."""
        # Create runs for multiple newspapers
        for name in ["fiji_sun", "fiji_sun", "khmer_times"]:
            run = tracker.start_run(
                newspaper=name,
                country="fiji" if "fiji" in name else "cambodia",
                mode="update",
            )
            tracker.complete_run(
                run.run_id,
                status="success",
                articles_scraped=10,
            )

        stats = tracker.get_newspaper_stats(days=30)
        assert len(stats) == 2

        fiji_stats = next(s for s in stats if s["newspaper"] == "fiji_sun")
        assert fiji_stats["total_runs"] == 2
        assert fiji_stats["total_articles"] == 20

    def test_cleanup_old_runs(self, tracker):
        """cleanup_old_runs should delete old runs."""
        # Create a run
        run = tracker.start_run(
            newspaper="fiji_sun",
            country="fiji",
            mode="update",
        )
        tracker.complete_run(run.run_id, status="success")
        tracker.record_article(run.run_id, url="https://example.com", status="success")

        # Manually update started_at to be old
        with tracker._connect() as conn:
            old_date = (datetime.utcnow() - timedelta(days=100)).isoformat()
            conn.execute(
                "UPDATE scraper_runs SET started_at = ? WHERE run_id = ?",
                (old_date, run.run_id),
            )

        deleted = tracker.cleanup_old_runs(days=90)
        assert deleted == 1

        assert tracker.get_run(run.run_id) is None


class TestComputeConfigHash:
    """Tests for the compute_config_hash function."""

    def test_computes_hash(self):
        """compute_config_hash should compute a hash of the file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("name: test\nkey: value\n")
            f.flush()

            hash1 = compute_config_hash(Path(f.name))
            assert len(hash1) == 12

            # Same content = same hash
            hash2 = compute_config_hash(Path(f.name))
            assert hash1 == hash2

        Path(f.name).unlink()

    def test_different_content_different_hash(self):
        """compute_config_hash should produce different hashes for different content."""
        hashes = []

        for content in ["content1", "content2"]:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(content)
                f.flush()
                hashes.append(compute_config_hash(Path(f.name)))
            Path(f.name).unlink()

        assert hashes[0] != hashes[1]
