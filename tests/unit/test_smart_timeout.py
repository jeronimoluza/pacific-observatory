"""Tests for smart timeout logic."""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.observability.progress import is_scraper_stale


class TestSmartTimeout:
    """Tests for is_scraper_stale function."""

    def test_no_progress_file_not_stale(self):
        """Scraper without progress file is not considered stale (still starting)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = is_scraper_stale("fiji", "fiji_sun", base_path=tmpdir)
            assert result is False

    def test_recent_activity_not_stale(self):
        """Scraper with recent activity is not stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_dir = Path(tmpdir) / "fiji" / "fiji_sun"
            progress_dir.mkdir(parents=True)
            progress_file = progress_dir / "progress.json"

            data = {
                "phase": "scraping",
                "last_activity": datetime.now().isoformat(),
                "urls_found": 10,
                "articles_scraped": 5,
                "articles_failed": 0,
            }
            progress_file.write_text(json.dumps(data))

            result = is_scraper_stale(
                "fiji",
                "fiji_sun",
                stale_threshold_seconds=120,
                base_path=tmpdir,
            )
            assert result is False

    def test_old_activity_is_stale(self):
        """Scraper with old activity is stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_dir = Path(tmpdir) / "fiji" / "fiji_sun"
            progress_dir.mkdir(parents=True)
            progress_file = progress_dir / "progress.json"

            old_time = datetime.now() - timedelta(seconds=300)
            data = {
                "phase": "scraping",
                "last_activity": old_time.isoformat(),
                "urls_found": 10,
                "articles_scraped": 5,
                "articles_failed": 0,
            }
            progress_file.write_text(json.dumps(data))

            result = is_scraper_stale(
                "fiji",
                "fiji_sun",
                stale_threshold_seconds=120,
                base_path=tmpdir,
            )
            assert result is True
