"""Unit tests for run summary output formatting."""

import sys
from pathlib import Path
import tempfile

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.orchestration.summary import format_run_summary, format_duration
from text.scrapers.orchestration.run_multiple import extract_article_count_from_log


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_format_duration_seconds(self):
        """Test formatting for durations less than 60 seconds."""
        assert format_duration(5) == "5 seconds"
        assert format_duration(30) == "30 seconds"
        assert format_duration(59) == "59 seconds"

    def test_format_duration_minutes(self):
        """Test formatting for durations 60 seconds or more."""
        assert format_duration(60) == "1 minutes"
        assert format_duration(120) == "2 minutes"
        assert format_duration(2820) == "47 minutes"
        assert format_duration(3600) == "60 minutes"


class TestFormatRunSummary:
    """Tests for run summary formatting."""

    def test_format_run_summary_with_mixed_results(self):
        """Test summary with success, failure, and timeout mixed."""
        results = [
            {
                "newspaper": "fiji_times",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 45.2,
                "articles_scraped": 150,
            },
            {
                "newspaper": "fiji_sun",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 38.5,
                "articles_scraped": 120,
            },
            {
                "newspaper": "post_courier",
                "country": "papua_new_guinea",
                "status": "timeout",
                "duration_seconds": 600.0,
                "error_msg": "Timeout after 600 seconds",
            },
            {
                "newspaper": "solomon_star",
                "country": "solomon_islands",
                "status": "failed",
                "duration_seconds": 15.3,
                "error_msg": "HTTP 503",
            },
            {
                "newspaper": "vanuatu_daily",
                "country": "vanuatu",
                "status": "failed",
                "duration_seconds": 8.1,
                "error_msg": "parse error",
            },
        ]

        total_duration = 2820  # 47 minutes

        summary = format_run_summary(results, total_duration)

        # Check header
        assert "=== Scrape Complete ===" in summary

        # Check success count and articles
        assert "Succeeded: 2 newspapers (270 articles)" in summary

        # Check failed count and details
        assert "Failed:    3 newspapers" in summary
        assert "  - post_courier: Timeout after 600 seconds" in summary
        assert "  - solomon_star: HTTP 503" in summary
        assert "  - vanuatu_daily: parse error" in summary

        # Check no skipped
        assert "Skipped:" not in summary

        # Check duration
        assert "Duration: 47 minutes" in summary

        # Check output directory
        assert "Output: data/text/" in summary

    def test_format_run_summary_all_success(self):
        """Test summary when all scrapers succeed."""
        results = [
            {
                "newspaper": "fiji_times",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 45.2,
                "articles_scraped": 150,
            },
            {
                "newspaper": "fiji_sun",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 38.5,
                "articles_scraped": 120,
            },
            {
                "newspaper": "samoa_observer",
                "country": "samoa",
                "status": "success",
                "duration_seconds": 52.1,
                "articles_scraped": 85,
            },
        ]

        total_duration = 150  # 2.5 minutes

        summary = format_run_summary(results, total_duration)

        # Check success with article count
        assert "Succeeded: 3 newspapers (355 articles)" in summary

        # Check no failed or skipped sections
        assert "Failed:" not in summary
        assert "Skipped:" not in summary

        # Check duration in minutes (150s = 2.5 min, but we format as 2 minutes)
        assert "Duration: 2 minutes" in summary

    def test_format_run_summary_all_failed(self):
        """Test summary when all scrapers fail."""
        results = [
            {
                "newspaper": "post_courier",
                "country": "papua_new_guinea",
                "status": "timeout",
                "duration_seconds": 600.0,
                "error_msg": "Timeout after 600 seconds",
            },
            {
                "newspaper": "solomon_star",
                "country": "solomon_islands",
                "status": "failed",
                "duration_seconds": 15.3,
                "error_msg": "HTTP 503",
            },
        ]

        total_duration = 45  # Less than 60 seconds

        summary = format_run_summary(results, total_duration)

        # Check no success
        assert "Succeeded:" not in summary

        # Check failed count and details
        assert "Failed:    2 newspapers" in summary
        assert "  - post_courier: Timeout after 600 seconds" in summary
        assert "  - solomon_star: HTTP 503" in summary

        # Check duration in seconds
        assert "Duration: 45 seconds" in summary

    def test_format_run_summary_with_skipped(self):
        """Test summary with skipped newspapers."""
        results = [
            {
                "newspaper": "fiji_times",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 45.2,
                "articles_scraped": 150,
            },
            {
                "newspaper": "fiji_sun",
                "country": "fiji",
                "status": "skipped",
                "duration_seconds": 0.0,
                "error_msg": "No new articles",
            },
        ]

        total_duration = 60

        summary = format_run_summary(results, total_duration)

        # Check skipped section
        assert "Skipped:   1 newspapers" in summary
        assert "Succeeded: 1 newspapers (150 articles)" in summary

    def test_format_run_summary_no_articles_scraped(self):
        """Test summary when articles_scraped is not present or zero."""
        results = [
            {
                "newspaper": "fiji_times",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 45.2,
                # No articles_scraped field
            },
            {
                "newspaper": "fiji_sun",
                "country": "fiji",
                "status": "success",
                "duration_seconds": 38.5,
                "articles_scraped": 0,
            },
        ]

        total_duration = 100

        summary = format_run_summary(results, total_duration)

        # Should show newspaper count but no article count
        assert "Succeeded: 2 newspapers" in summary
        # Should not show articles when total is 0
        assert "(0 articles)" not in summary


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
