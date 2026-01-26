"""Unit tests for run summary output formatting."""

import sys
from pathlib import Path
import tempfile

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.observability import format_duration
from text.scrapers.orchestration.run_multiple import extract_article_count_from_log


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_format_duration_seconds(self):
        """Test formatting for durations less than 60 seconds."""
        assert format_duration(5) == "5s"
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"

    def test_format_duration_minutes(self):
        """Test formatting for durations 60 seconds or more but less than an hour."""
        assert format_duration(60) == "1m 0s"
        assert format_duration(120) == "2m 0s"
        assert format_duration(2820) == "47m 0s"
        assert format_duration(154) == "2m 34s"

    def test_format_duration_hours(self):
        """Test formatting for durations an hour or more."""
        assert format_duration(3600) == "1h 0m"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(4500) == "1h 15m"
        assert format_duration(7200) == "2h 0m"


class TestExtractArticleCountFromLog:
    """Tests for article count extraction from log files."""

    def test_extract_scraped_articles_from_pattern(self):
        """Test extracting article count from 'Scraped N articles from' pattern."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write("2026-01-22 10:00:00 - INFO - Starting scraper\n")
            f.write(
                "2026-01-22 10:05:00 - INFO - Scraped 150 articles from 200 thumbnails (5 failed)\n"
            )
            f.write("2026-01-22 10:06:00 - INFO - Scraping completed\n")
            log_path = Path(f.name)

        try:
            count = extract_article_count_from_log(log_path)
            assert count == 150
        finally:
            log_path.unlink()

    def test_extract_articles_scraped_pattern(self):
        """Test extracting article count from 'N articles scraped' pattern."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write("2026-01-22 10:00:00 - INFO - Starting scraper\n")
            f.write(
                "2026-01-22 10:05:00 - INFO - DEFAULT mode completed: 45 new URLs, 120 articles scraped\n"
            )
            f.write("2026-01-22 10:06:00 - INFO - Scraping completed\n")
            log_path = Path(f.name)

        try:
            count = extract_article_count_from_log(log_path)
            assert count == 120
        finally:
            log_path.unlink()

    def test_extract_returns_zero_for_missing_pattern(self):
        """Test that extraction returns 0 when no pattern matches."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write("2026-01-22 10:00:00 - INFO - Starting scraper\n")
            f.write("2026-01-22 10:01:00 - ERROR - Failed to scrape\n")
            log_path = Path(f.name)

        try:
            count = extract_article_count_from_log(log_path)
            assert count == 0
        finally:
            log_path.unlink()

    def test_extract_returns_zero_for_missing_file(self):
        """Test that extraction returns 0 for non-existent file."""
        non_existent = Path("/fake/path/to/log.log")
        count = extract_article_count_from_log(non_existent)
        assert count == 0

    def test_extract_prefers_first_pattern_match(self):
        """Test that first matching pattern is used."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            f.write(
                "2026-01-22 10:00:00 - INFO - Scraped 150 articles from 200 thumbnails\n"
            )
            f.write(
                "2026-01-22 10:01:00 - INFO - Some other log with 75 articles scraped\n"
            )
            log_path = Path(f.name)

        try:
            # Should match first "Scraped N articles from" pattern
            count = extract_article_count_from_log(log_path)
            assert count == 150
        finally:
            log_path.unlink()
