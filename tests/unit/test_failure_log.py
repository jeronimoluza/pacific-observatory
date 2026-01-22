"""Unit tests for failure logging in scraper orchestration."""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.orchestration.failure_log import (
    classify_failure_reason,
    write_failure_log,
)


class TestClassifyFailureReason:
    """Tests for failure reason classification."""

    def test_classify_failure_reason_timeout(self):
        """Test that timeout status is correctly classified."""
        result = {
            "newspaper": "post_courier",
            "country": "papua_new_guinea",
            "status": "timeout",
            "duration_seconds": 600.0,
            "error_msg": "Timeout after 600 seconds",
        }
        reason = classify_failure_reason(result)
        assert reason == "timeout"

    def test_classify_failure_reason_http_403(self):
        """Test that HTTP 403 error is classified as http_error."""
        result = {
            "newspaper": "solomon_star",
            "country": "solomon_islands",
            "status": "failed",
            "duration_seconds": 30.5,
            "error_msg": "HTTP 403 Forbidden",
        }
        reason = classify_failure_reason(result)
        assert reason == "http_error"

    def test_classify_failure_reason_http_404(self):
        """Test that HTTP 404 error is classified as http_error."""
        result = {
            "newspaper": "fiji_times",
            "country": "fiji",
            "status": "failed",
            "duration_seconds": 15.2,
            "error_msg": "HTTP 404 Not Found",
        }
        reason = classify_failure_reason(result)
        assert reason == "http_error"

    def test_classify_failure_reason_http_500(self):
        """Test that HTTP 500 error is classified as http_error."""
        result = {
            "newspaper": "vanuatu_daily",
            "country": "vanuatu",
            "status": "failed",
            "duration_seconds": 25.0,
            "error_msg": "Server error: 500 Internal Server Error",
        }
        reason = classify_failure_reason(result)
        assert reason == "http_error"

    def test_classify_failure_reason_http_503(self):
        """Test that HTTP 503 error is classified as http_error."""
        result = {
            "newspaper": "samoa_observer",
            "country": "samoa",
            "status": "failed",
            "duration_seconds": 10.5,
            "error_msg": "HTTP 503 Service Unavailable",
        }
        reason = classify_failure_reason(result)
        assert reason == "http_error"

    def test_classify_failure_reason_http_lowercase(self):
        """Test that http errors are matched case-insensitively."""
        result = {
            "newspaper": "fiji_sun",
            "country": "fiji",
            "status": "failed",
            "duration_seconds": 20.0,
            "error_msg": "http error occurred",
        }
        reason = classify_failure_reason(result)
        assert reason == "http_error"

    def test_classify_failure_reason_parse_error(self):
        """Test that parse error is correctly classified."""
        result = {
            "newspaper": "tonga_chronicle",
            "country": "tonga",
            "status": "failed",
            "duration_seconds": 45.5,
            "error_msg": "Failed to parse article content",
        }
        reason = classify_failure_reason(result)
        assert reason == "parse_error"

    def test_classify_failure_reason_no_articles(self):
        """Test that 'no articles' error is classified as parse_error."""
        result = {
            "newspaper": "kiribati_news",
            "country": "kiribati",
            "status": "failed",
            "duration_seconds": 30.0,
            "error_msg": "No articles found on page",
        }
        reason = classify_failure_reason(result)
        assert reason == "parse_error"

    def test_classify_failure_reason_selector(self):
        """Test that selector error is classified as parse_error."""
        result = {
            "newspaper": "marshall_journal",
            "country": "marshall_islands",
            "status": "failed",
            "duration_seconds": 35.0,
            "error_msg": "Selector not found: .article-content",
        }
        reason = classify_failure_reason(result)
        assert reason == "parse_error"

    def test_classify_failure_reason_extraction(self):
        """Test that extraction error is classified as parse_error."""
        result = {
            "newspaper": "palau_horizon",
            "country": "palau",
            "status": "failed",
            "duration_seconds": 40.0,
            "error_msg": "Extraction failed for title field",
        }
        reason = classify_failure_reason(result)
        assert reason == "parse_error"

    def test_classify_failure_reason_process_error(self):
        """Test that exit code error is classified as process_error."""
        result = {
            "newspaper": "nauru_bulletin",
            "country": "nauru",
            "status": "failed",
            "duration_seconds": 5.0,
            "error_msg": "Process exited with exit code 1",
        }
        reason = classify_failure_reason(result)
        assert reason == "process_error"

    def test_classify_failure_reason_unknown(self):
        """Test that unknown errors are classified as unknown."""
        result = {
            "newspaper": "tuvalu_times",
            "country": "tuvalu",
            "status": "failed",
            "duration_seconds": 12.0,
            "error_msg": "Something unexpected happened",
        }
        reason = classify_failure_reason(result)
        assert reason == "unknown"

    def test_classify_failure_reason_no_error_msg(self):
        """Test classification when error_msg is missing."""
        result = {
            "newspaper": "fsm_news",
            "country": "micronesia",
            "status": "failed",
            "duration_seconds": 8.0,
        }
        reason = classify_failure_reason(result)
        assert reason == "unknown"


class TestWriteFailureLog:
    """Tests for write_failure_log function."""

    def test_write_failure_log_creates_json(self):
        """Test that failure log JSON file is created with correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "last_run_failures.json"

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
                    "duration_seconds": 30.5,
                    "error_msg": "HTTP 503",
                },
            ]

            write_failure_log(results, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify JSON structure
            with open(output_path, "r") as f:
                data = json.load(f)

            assert "run_timestamp" in data
            assert "failures" in data
            assert len(data["failures"]) == 2

            # Verify first failure
            failure1 = data["failures"][0]
            assert failure1["newspaper"] == "post_courier"
            assert failure1["country"] == "papua_new_guinea"
            assert failure1["reason"] == "timeout"
            assert failure1["duration_seconds"] == 600.0
            assert failure1["error_msg"] == "Timeout after 600 seconds"

            # Verify second failure
            failure2 = data["failures"][1]
            assert failure2["newspaper"] == "solomon_star"
            assert failure2["country"] == "solomon_islands"
            assert failure2["reason"] == "http_error"
            assert failure2["duration_seconds"] == 30.5
            assert failure2["error_msg"] == "HTTP 503"

    def test_write_failure_log_no_failures(self):
        """Test that empty failures array is written when all succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "last_run_failures.json"

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
            ]

            write_failure_log(results, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify JSON structure
            with open(output_path, "r") as f:
                data = json.load(f)

            assert "run_timestamp" in data
            assert "failures" in data
            assert len(data["failures"]) == 0

    def test_write_failure_log_creates_parent_directories(self):
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested path
            output_path = Path(tmpdir) / "data" / "text" / "last_run_failures.json"

            results = [
                {
                    "newspaper": "solomon_star",
                    "country": "solomon_islands",
                    "status": "failed",
                    "duration_seconds": 30.5,
                    "error_msg": "HTTP 503",
                },
            ]

            write_failure_log(results, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify parent directories were created
            assert output_path.parent.exists()

    def test_write_failure_log_mixed_results(self):
        """Test that only failures are logged, not successes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "last_run_failures.json"

            results = [
                {
                    "newspaper": "fiji_times",
                    "country": "fiji",
                    "status": "success",
                    "duration_seconds": 45.2,
                    "articles_scraped": 150,
                },
                {
                    "newspaper": "post_courier",
                    "country": "papua_new_guinea",
                    "status": "timeout",
                    "duration_seconds": 600.0,
                    "error_msg": "Timeout after 600 seconds",
                },
                {
                    "newspaper": "fiji_sun",
                    "country": "fiji",
                    "status": "success",
                    "duration_seconds": 38.5,
                    "articles_scraped": 120,
                },
                {
                    "newspaper": "solomon_star",
                    "country": "solomon_islands",
                    "status": "failed",
                    "duration_seconds": 30.5,
                    "error_msg": "HTTP 503",
                },
            ]

            write_failure_log(results, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify JSON structure
            with open(output_path, "r") as f:
                data = json.load(f)

            # Only 2 failures should be logged (not the 2 successes)
            assert len(data["failures"]) == 2
            assert data["failures"][0]["newspaper"] == "post_courier"
            assert data["failures"][1]["newspaper"] == "solomon_star"

    def test_write_failure_log_timestamp_format(self):
        """Test that timestamp is in ISO format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "last_run_failures.json"

            results = [
                {
                    "newspaper": "solomon_star",
                    "country": "solomon_islands",
                    "status": "failed",
                    "duration_seconds": 30.5,
                    "error_msg": "HTTP 503",
                },
            ]

            write_failure_log(results, output_path)

            with open(output_path, "r") as f:
                data = json.load(f)

            # Verify timestamp is in ISO format by parsing it
            timestamp = data["run_timestamp"]
            # This will raise an exception if not valid ISO format
            datetime.fromisoformat(timestamp)

    def test_write_failure_log_json_formatting(self):
        """Test that JSON is properly formatted with indentation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "last_run_failures.json"

            results = [
                {
                    "newspaper": "solomon_star",
                    "country": "solomon_islands",
                    "status": "failed",
                    "duration_seconds": 30.5,
                    "error_msg": "HTTP 503",
                },
            ]

            write_failure_log(results, output_path)

            # Read the raw file content
            content = output_path.read_text()

            # Verify it's properly indented (should have newlines and spaces)
            assert "\n" in content
            assert "  " in content  # 2-space indentation
