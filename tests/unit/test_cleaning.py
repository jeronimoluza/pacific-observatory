"""Unit tests for the cleaning module."""

from pathlib import Path
from datetime import datetime

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from text.scrapers.pipelines.cleaning import (
    handle_mixed_dates,
    clean_html_text,
    normalize_tags,
    clean_url,
    clean_title,
    clean_kosmo_body,
    clean_the_independent_body,
    clean_philstar_body,
    clean_inquirer_body,
    get_cleaning_func,
    apply_cleaning,
    CLEANING_FUNCTIONS,
)


class TestHandleMixedDates:
    """Tests for the handle_mixed_dates function."""

    def test_iso_format(self):
        """Should parse ISO format dates."""
        assert handle_mixed_dates("2024-01-15") == "2024-01-15"

    def test_slash_format(self):
        """Should parse slash-separated dates."""
        assert handle_mixed_dates("2024/01/15") == "2024-01-15"

    def test_full_month_name_with_comma(self):
        """Should parse 'Month DD, YYYY' format."""
        assert handle_mixed_dates("January 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("September 24, 2025") == "2025-09-24"

    def test_abbreviated_month(self):
        """Should parse abbreviated month names."""
        assert handle_mixed_dates("Jan 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("Sep 24, 2025") == "2025-09-24"

    def test_day_first_format(self):
        """Should parse 'DD Month YYYY' format."""
        assert handle_mixed_dates("15 January 2024") == "2024-01-15"
        assert handle_mixed_dates("24 Sep 2025") == "2025-09-24"

    def test_with_weekday(self):
        """Should parse dates with weekday names."""
        assert handle_mixed_dates("Monday, January 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("Mon, Jan 15, 2024") == "2024-01-15"

    def test_with_time(self):
        """Should parse dates with time components."""
        assert handle_mixed_dates("January 15, 2024 14:30") == "2024-01-15"
        assert handle_mixed_dates("2024-01-15T14:30:00") == "2024-01-15"
        assert handle_mixed_dates("2024-01-15T14:30:00Z") == "2024-01-15"

    def test_unix_timestamp_int(self):
        """Should parse Unix timestamps as integers."""
        timestamp = int(datetime(2024, 1, 15).timestamp())
        assert handle_mixed_dates(timestamp) == "2024-01-15"

    def test_unix_timestamp_string(self):
        """Should parse Unix timestamps as strings."""
        timestamp = str(int(datetime(2024, 1, 15).timestamp()))
        assert handle_mixed_dates(timestamp) == "2024-01-15"

    def test_with_prefix(self):
        """Should handle dates with common prefixes."""
        assert handle_mixed_dates("Published: January 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("Posted: Jan 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("Date: 2024-01-15") == "2024-01-15"

    def test_with_bullet_prefix(self):
        """Should handle dates with bullet/dash prefixes."""
        assert handle_mixed_dates("- January 15, 2024") == "2024-01-15"
        assert handle_mixed_dates("• Jan 15, 2024") == "2024-01-15"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert handle_mixed_dates("") == ""
        assert handle_mixed_dates(None) == ""

    def test_dotted_format(self):
        """Should parse dot-separated dates."""
        assert handle_mixed_dates("15.01.2024") == "2024-01-15"

    def test_extracts_date_from_text(self):
        """Should extract date from surrounding text."""
        result = handle_mixed_dates("Some text January 15, 2024 more text")
        assert result == "2024-01-15"


class TestCleanHtmlText:
    """Tests for the clean_html_text function."""

    def test_removes_extra_whitespace(self):
        """Should collapse multiple spaces."""
        assert clean_html_text("Hello   world") == "Hello world"

    def test_removes_newlines(self):
        """Should collapse newlines to spaces."""
        assert clean_html_text("Hello\n\nworld") == "Hello world"

    def test_strips_text(self):
        """Should strip leading/trailing whitespace."""
        assert clean_html_text("  Hello world  ") == "Hello world"

    def test_decodes_html_entities(self):
        """Should decode HTML entities."""
        assert clean_html_text("&amp;") == "&"
        assert clean_html_text("&lt;") == "<"
        assert clean_html_text("&gt;") == ">"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert clean_html_text("") == ""
        assert clean_html_text(None) == ""


class TestNormalizeTags:
    """Tests for the normalize_tags function."""

    def test_splits_comma_separated(self):
        """Should split comma-separated tags."""
        assert normalize_tags("tag1, tag2, tag3") == ["tag1", "tag2", "tag3"]

    def test_splits_semicolon_separated(self):
        """Should split semicolon-separated tags."""
        assert normalize_tags("tag1; tag2; tag3") == ["tag1", "tag2", "tag3"]

    def test_splits_pipe_separated(self):
        """Should split pipe-separated tags."""
        assert normalize_tags("tag1 | tag2 | tag3") == ["tag1", "tag2", "tag3"]

    def test_removes_duplicates(self):
        """Should remove duplicate tags."""
        assert normalize_tags("tag1, tag1, tag2") == ["tag1", "tag2"]

    def test_strips_whitespace(self):
        """Should strip whitespace from tags."""
        assert normalize_tags("  tag1  ,  tag2  ") == ["tag1", "tag2"]

    def test_empty_string(self):
        """Should handle empty strings."""
        assert normalize_tags("") == []
        assert normalize_tags(None) == []


class TestCleanUrl:
    """Tests for the clean_url function."""

    def test_preserves_absolute_urls(self):
        """Should preserve absolute URLs."""
        url = "https://example.com/path"
        assert clean_url(url) == url

    def test_makes_relative_urls_absolute(self):
        """Should make relative URLs absolute with base_url."""
        assert (
            clean_url("/path/to/page", "https://example.com")
            == "https://example.com/path/to/page"
        )

    def test_strips_whitespace(self):
        """Should strip whitespace."""
        assert clean_url("  https://example.com  ") == "https://example.com"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert clean_url("") == ""
        assert clean_url(None) == ""


class TestCleanTitle:
    """Tests for the clean_title function."""

    def test_removes_extra_whitespace(self):
        """Should collapse multiple spaces."""
        assert clean_title("Hello   world") == "Hello world"

    def test_strips_punctuation(self):
        """Should strip leading/trailing punctuation."""
        assert clean_title(" - Hello world - ") == "Hello world"
        assert clean_title("| Hello world |") == "Hello world"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert clean_title("") == ""
        assert clean_title(None) == ""


class TestNewspaperSpecificCleaners:
    """Tests for newspaper-specific cleaning functions."""

    def test_clean_kosmo_body(self):
        """Should remove Kosmo footer text."""
        body = "Article content. – KOSMO! ONLINE Hak cipta terpelihara"
        result = clean_kosmo_body(
            body
            + " © 2026 Media Mulia Sdn Bhd 201801030285 (1292311-H) Satu lagi produk Media Mulia Sdn."
        )
        assert "KOSMO! ONLINE Hak cipta" not in result
        assert "Article content" in result

    def test_clean_the_independent_body(self):
        """Should remove Independent signature and Read also sections."""
        body = "Article content./TISG Read also: Other article"
        result = clean_the_independent_body(body)
        assert "/TISG" not in result
        assert "Read also" not in result

    def test_clean_philstar_body(self):
        """Should handle Philstar format."""
        body = "MANILA – The government announced new policies."
        result = clean_philstar_body(body)
        assert result.startswith("The government")

    def test_clean_inquirer_body(self):
        """Should remove Inquirer newsletter signup and READ sections."""
        body = "Content. Subscribe to our daily newsletter By providing an email address. I agree to the Terms of Use and acknowledge that I have read the Privacy Policy READ: Another article."
        result = clean_inquirer_body(body)
        assert "Subscribe to our daily newsletter" not in result
        assert "READ:" not in result


class TestGetCleaningFunc:
    """Tests for the get_cleaning_func function."""

    def test_returns_function(self):
        """Should return the cleaning function."""
        func = get_cleaning_func("handle_mixed_dates")
        assert func is handle_mixed_dates

    def test_returns_none_for_unknown(self):
        """Should return None for unknown function names."""
        assert get_cleaning_func("nonexistent_function") is None

    def test_all_registered_functions_exist(self):
        """All registered functions should be callable."""
        for name, func in CLEANING_FUNCTIONS.items():
            assert callable(func), f"Function {name} is not callable"


class TestApplyCleaning:
    """Tests for the apply_cleaning function."""

    def test_applies_cleaning_functions(self):
        """Should apply cleaning functions to data."""
        data = {"date": "January 15, 2024", "title": "  Hello World  "}
        config = {"date": "handle_mixed_dates", "title": "clean_title"}

        result = apply_cleaning(data, config)

        assert result["date"] == "2024-01-15"
        assert result["title"] == "Hello World"

    def test_preserves_unconfigured_fields(self):
        """Should preserve fields without cleaning config."""
        data = {"date": "January 15, 2024", "body": "Some content"}
        config = {"date": "handle_mixed_dates"}

        result = apply_cleaning(data, config)

        assert result["body"] == "Some content"

    def test_handles_missing_fields(self):
        """Should handle fields not in data."""
        data = {"title": "Hello"}
        config = {"date": "handle_mixed_dates", "title": "clean_title"}

        result = apply_cleaning(data, config)

        assert result["title"] == "Hello"
        assert "date" not in result

    def test_handles_unknown_functions(self):
        """Should handle unknown function names gracefully."""
        data = {"title": "Hello"}
        config = {"title": "unknown_function"}

        result = apply_cleaning(data, config)
        assert result["title"] == "Hello"  # Unchanged

    def test_handles_empty_config(self):
        """Should handle empty config."""
        data = {"title": "Hello"}
        result = apply_cleaning(data, {})
        assert result == data

    def test_handles_none_data(self):
        """Should handle None data."""
        result = apply_cleaning(None, {"title": "clean_title"})
        assert result is None

    def test_passes_base_url_to_clean_url(self):
        """Should pass base_url to clean_url function."""
        data = {"url": "/path/to/page"}
        config = {"url": "clean_url"}

        result = apply_cleaning(data, config, base_url="https://example.com")

        assert result["url"] == "https://example.com/path/to/page"
