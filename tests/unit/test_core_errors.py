"""Unit tests for the error hierarchy module."""

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.core.errors import (
    TextModuleError,
    ScraperError,
    NetworkError,
    RateLimitError,
    ParseError,
    ConfigError,
    StorageError,
    AnalysisError,
    CircuitOpenError,
    CheckpointError,
)


class TestTextModuleError:
    """Tests for the base TextModuleError class."""

    def test_stores_message(self):
        """Should store the error message."""
        error = TextModuleError("Something went wrong")
        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"

    def test_stores_context(self):
        """Should store context dictionary."""
        error = TextModuleError("Error", context={"key": "value"})
        assert error.context == {"key": "value"}

    def test_includes_context_in_str(self):
        """Should include context in string representation."""
        error = TextModuleError("Error", context={"key": "value"})
        assert "key=value" in str(error)

    def test_empty_context_defaults(self):
        """Should default to empty context."""
        error = TextModuleError("Error")
        assert error.context == {}


class TestScraperError:
    """Tests for the ScraperError class."""

    def test_stores_newspaper(self):
        """Should store newspaper name."""
        error = ScraperError("Failed", newspaper="fiji_sun")
        assert error.newspaper == "fiji_sun"
        assert "fiji_sun" in str(error)

    def test_stores_url(self):
        """Should store URL."""
        error = ScraperError("Failed", url="https://example.com")
        assert error.url == "https://example.com"
        assert "example.com" in str(error)

    def test_combines_context(self):
        """Should combine newspaper, url, and additional context."""
        error = ScraperError(
            "Failed",
            newspaper="fiji_sun",
            url="https://example.com",
            context={"extra": "info"},
        )
        assert error.context["newspaper"] == "fiji_sun"
        assert error.context["url"] == "https://example.com"
        assert error.context["extra"] == "info"


class TestNetworkError:
    """Tests for the NetworkError class."""

    def test_stores_status_code(self):
        """Should store HTTP status code."""
        error = NetworkError("Request failed", status_code=404)
        assert error.status_code == 404
        assert "404" in str(error)

    def test_stores_retry_count(self):
        """Should store retry count."""
        error = NetworkError("Request failed", retry_count=3)
        assert error.retry_count == 3

    def test_includes_all_context(self):
        """Should include all context fields."""
        error = NetworkError(
            "Failed",
            status_code=500,
            retry_count=3,
            newspaper="fiji_sun",
        )
        assert error.context["status_code"] == 500
        assert error.context["retry_count"] == 3
        assert error.context["newspaper"] == "fiji_sun"


class TestRateLimitError:
    """Tests for the RateLimitError class."""

    def test_defaults_to_429(self):
        """Should default to status code 429."""
        error = RateLimitError("Rate limited")
        assert error.status_code == 429

    def test_stores_retry_after(self):
        """Should store retry_after value."""
        error = RateLimitError("Rate limited", retry_after=60)
        assert error.retry_after == 60
        assert "60" in str(error)


class TestParseError:
    """Tests for the ParseError class."""

    def test_stores_selector(self):
        """Should store CSS/XPath selector."""
        error = ParseError("Selector not found", selector="div.article-body")
        assert error.selector == "div.article-body"
        assert "div.article-body" in str(error)

    def test_stores_content_preview(self):
        """Should store content preview."""
        error = ParseError("Parse failed", content_preview="<html>...")
        assert error.content_preview == "<html>..."


class TestConfigError:
    """Tests for the ConfigError class."""

    def test_stores_config_path(self):
        """Should store config path."""
        error = ConfigError("Invalid config", config_path="/path/to/config.yaml")
        assert error.config_path == "/path/to/config.yaml"

    def test_stores_field(self):
        """Should store field name."""
        error = ConfigError("Missing field", field="base_url")
        assert error.field == "base_url"


class TestStorageError:
    """Tests for the StorageError class."""

    def test_stores_file_path(self):
        """Should store file path."""
        error = StorageError("Write failed", file_path="/data/news.csv")
        assert error.file_path == "/data/news.csv"


class TestAnalysisError:
    """Tests for the AnalysisError class."""

    def test_stores_newspaper_and_country(self):
        """Should store newspaper and country."""
        error = AnalysisError(
            "Analysis failed",
            newspaper="fiji_sun",
            country="fiji",
        )
        assert error.newspaper == "fiji_sun"
        assert error.country == "fiji"


class TestCircuitOpenError:
    """Tests for the CircuitOpenError class."""

    def test_stores_recovery_time(self):
        """Should store recovery time."""
        error = CircuitOpenError(
            "Circuit open",
            recovery_time="2024-01-15T10:30:00",
        )
        assert error.recovery_time == "2024-01-15T10:30:00"


class TestCheckpointError:
    """Tests for the CheckpointError class."""

    def test_stores_run_id(self):
        """Should store run ID."""
        error = CheckpointError("Checkpoint failed", run_id="abc123")
        assert error.run_id == "abc123"


class TestExceptionHierarchy:
    """Tests for the exception hierarchy."""

    def test_scraper_error_is_text_module_error(self):
        """ScraperError should be a subclass of TextModuleError."""
        error = ScraperError("Failed")
        assert isinstance(error, TextModuleError)

    def test_network_error_is_scraper_error(self):
        """NetworkError should be a subclass of ScraperError."""
        error = NetworkError("Failed")
        assert isinstance(error, ScraperError)
        assert isinstance(error, TextModuleError)

    def test_rate_limit_error_is_network_error(self):
        """RateLimitError should be a subclass of NetworkError."""
        error = RateLimitError("Rate limited")
        assert isinstance(error, NetworkError)
        assert isinstance(error, ScraperError)
        assert isinstance(error, TextModuleError)

    def test_parse_error_is_scraper_error(self):
        """ParseError should be a subclass of ScraperError."""
        error = ParseError("Parse failed")
        assert isinstance(error, ScraperError)

    def test_can_catch_by_base_class(self):
        """Should be able to catch specific errors by base class."""
        errors = [
            NetworkError("Network failed"),
            RateLimitError("Rate limited"),
            ParseError("Parse failed"),
        ]

        for error in errors:
            try:
                raise error
            except ScraperError:
                # All should be caught by ScraperError
                pass
