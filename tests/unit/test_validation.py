"""
Tests for the newspaper scraper configuration validation CLI.

Tests validation functions for YAML syntax, required fields, URL connectivity,
and selector testing.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from text.scrapers.orchestration.validate import (
    validate_yaml_syntax,
    validate_required_fields,
    validate_url_reachable,
    validate_selectors_find_content,
    validate_config_comprehensive,
)


@pytest.fixture
def valid_config_dict():
    """Return a valid configuration dictionary."""
    return {
        "name": "Test Newspaper",
        "country": "test",
        "base_url": "https://example.com",
        "listing": {
            "type": "pagination",
            "start_url": "/news",
        },
        "selectors": {
            "thumbnail": {
                "container": ".article-card",
                "title": ".title",
                "url": "a",
                "date": ".date",
            },
            "article": {
                "body": ".article-body",
                "tags": ".tag",
            },
        },
        "cleaning": {
            "date": "handle_mixed_dates",
            "body": "clean_html_text",
        },
    }


@pytest.fixture
def valid_config_file(valid_config_dict):
    """Create a temporary valid configuration file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(valid_config_dict, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def invalid_yaml_file():
    """Create a temporary file with invalid YAML syntax."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("invalid: yaml: syntax: [[[")
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestValidateYAMLSyntax:
    """Tests for validate_yaml_syntax function."""

    def test_validate_yaml_syntax_valid(self, valid_config_file):
        """Test validation of valid YAML file."""
        result = validate_yaml_syntax(valid_config_file)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert "config" in result

    def test_validate_yaml_syntax_invalid(self, invalid_yaml_file):
        """Test validation of invalid YAML file."""
        result = validate_yaml_syntax(invalid_yaml_file)

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "YAML" in result["errors"][0] or "syntax" in result["errors"][0].lower()

    def test_validate_yaml_syntax_file_not_found(self):
        """Test validation when file doesn't exist."""
        result = validate_yaml_syntax(Path("/nonexistent/file.yaml"))

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert (
            "not found" in result["errors"][0].lower()
            or "no such file" in result["errors"][0].lower()
        )

    def test_validate_yaml_syntax_empty_file(self):
        """Test validation of empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = validate_yaml_syntax(temp_path)

            assert result["valid"] is False
            assert len(result["errors"]) > 0
            assert "empty" in result["errors"][0].lower()
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestValidateRequiredFields:
    """Tests for validate_required_fields function."""

    def test_validate_required_fields_valid(self, valid_config_dict):
        """Test validation when all required fields are present."""
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_required_fields_missing_name(self, valid_config_dict):
        """Test validation when 'name' field is missing."""
        del valid_config_dict["name"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert any("name" in error.lower() for error in result["errors"])

    def test_validate_required_fields_missing_country(self, valid_config_dict):
        """Test validation when 'country' field is missing."""
        del valid_config_dict["country"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert any("country" in error.lower() for error in result["errors"])

    def test_validate_required_fields_missing_base_url(self, valid_config_dict):
        """Test validation when 'base_url' field is missing."""
        del valid_config_dict["base_url"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert any("base_url" in error.lower() for error in result["errors"])

    def test_validate_required_fields_missing_listing(self, valid_config_dict):
        """Test validation when 'listing' field is missing."""
        del valid_config_dict["listing"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert any("listing" in error.lower() for error in result["errors"])

    def test_validate_required_fields_missing_selectors(self, valid_config_dict):
        """Test validation when 'selectors' field is missing."""
        del valid_config_dict["selectors"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert any("selectors" in error.lower() for error in result["errors"])

    def test_validate_required_fields_multiple_missing(self, valid_config_dict):
        """Test validation when multiple required fields are missing."""
        del valid_config_dict["name"]
        del valid_config_dict["base_url"]
        result = validate_required_fields(valid_config_dict)

        assert result["valid"] is False
        assert len(result["errors"]) >= 2


class TestValidateURLReachable:
    """Tests for validate_url_reachable function."""

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_url_reachable_success(self, mock_client_class):
        """Test validation when URL is reachable (200 OK)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = validate_url_reachable("https://example.com")

        assert result["reachable"] is True
        assert result["status_code"] == 200
        assert result.get("error") is None

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_url_reachable_404(self, mock_client_class):
        """Test validation when URL returns 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = validate_url_reachable("https://example.com")

        assert result["reachable"] is False
        assert result["status_code"] == 404

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_url_reachable_connection_error(self, mock_client_class):
        """Test validation when connection fails."""
        import httpx

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_class.return_value = mock_client

        result = validate_url_reachable("https://example.com")

        assert result["reachable"] is False
        assert result.get("error") is not None
        assert (
            "connection" in result["error"].lower()
            or "connect" in result["error"].lower()
        )

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_url_reachable_timeout(self, mock_client_class):
        """Test validation when request times out."""
        import httpx

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_client_class.return_value = mock_client

        result = validate_url_reachable("https://example.com", timeout=1)

        assert result["reachable"] is False
        assert result.get("error") is not None
        assert "timeout" in result["error"].lower()

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_url_reachable_custom_timeout(self, mock_client_class):
        """Test validation with custom timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = validate_url_reachable("https://example.com", timeout=10)

        assert result["reachable"] is True
        # Verify timeout was passed to client
        mock_client_class.assert_called_once_with(timeout=10, follow_redirects=True)


class TestValidateSelectorsFind:
    """Tests for validate_selectors_find_content function."""

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_selectors_find_content_success(self, mock_client_class):
        """Test validation when selectors find content."""
        html_content = """
        <html>
            <body>
                <div class="article-card">Article 1</div>
                <div class="article-card">Article 2</div>
                <div class="article-card">Article 3</div>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        config = {
            "selectors": {
                "thumbnail": {
                    "container": ".article-card",
                }
            }
        }

        result = validate_selectors_find_content(config, "https://example.com")

        assert result["valid"] is True
        assert result["found_count"] == 3
        assert result["selector"] == ".article-card"

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_selectors_find_content_no_matches(self, mock_client_class):
        """Test validation when selectors don't find content."""
        html_content = """
        <html>
            <body>
                <p>No articles here</p>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        config = {
            "selectors": {
                "thumbnail": {
                    "container": ".article-card",
                }
            }
        }

        result = validate_selectors_find_content(config, "https://example.com")

        assert result["valid"] is False
        assert result["found_count"] == 0

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_selectors_find_content_connection_error(self, mock_client_class):
        """Test validation when URL cannot be fetched."""
        import httpx

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_class.return_value = mock_client

        config = {
            "selectors": {
                "thumbnail": {
                    "container": ".article-card",
                }
            }
        }

        result = validate_selectors_find_content(config, "https://example.com")

        assert result["valid"] is False
        assert result.get("error") is not None

    def test_validate_selectors_find_content_no_selectors(self):
        """Test validation when config has no selectors."""
        config = {}

        result = validate_selectors_find_content(config, "https://example.com")

        assert result["valid"] is False
        assert result.get("error") is not None
        assert (
            "no selectors" in result["error"].lower()
            or "selectors not found" in result["error"].lower()
        )


class TestValidateConfigComprehensive:
    """Tests for validate_config_comprehensive function."""

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_config_comprehensive_all_pass(
        self, mock_client_class, valid_config_file
    ):
        """Test comprehensive validation when all checks pass."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<div class="article-card">Article</div>'
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = validate_config_comprehensive(valid_config_file)

        assert result["overall_valid"] is True
        assert "sections" in result
        assert result["sections"]["syntax"]["valid"] is True
        assert result["sections"]["required_fields"]["valid"] is True

    def test_validate_config_comprehensive_syntax_fail(self, invalid_yaml_file):
        """Test comprehensive validation when YAML syntax fails."""
        result = validate_config_comprehensive(invalid_yaml_file)

        assert result["overall_valid"] is False
        assert result["sections"]["syntax"]["valid"] is False

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_config_comprehensive_missing_fields(self, mock_client_class):
        """Test comprehensive validation when required fields are missing."""
        config_dict = {
            "name": "Test",
            # Missing country and base_url
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_dict, f)
            temp_path = Path(f.name)

        try:
            result = validate_config_comprehensive(temp_path)

            assert result["overall_valid"] is False
            assert result["sections"]["required_fields"]["valid"] is False
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_config_comprehensive_with_warnings(
        self, mock_client_class, valid_config_file
    ):
        """Test comprehensive validation with warnings about missing cleaning functions."""
        # Modify config to use non-existent cleaning function
        with open(valid_config_file) as f:
            config = yaml.safe_load(f)

        config["cleaning"]["date"] = "nonexistent_cleaning_function"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            temp_path = Path(f.name)

        try:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '<div class="article-card">Article</div>'
            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.get = Mock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = validate_config_comprehensive(temp_path)

            # Should still pass overall but have warnings
            assert "warnings" in result["sections"]
            assert len(result["sections"]["warnings"]) > 0
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @patch("text.scrapers.orchestration.validate.httpx.Client")
    def test_validate_config_comprehensive_url_unreachable(
        self, mock_client_class, valid_config_file
    ):
        """Test comprehensive validation when base URL is unreachable."""
        import httpx

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.get = Mock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_class.return_value = mock_client

        result = validate_config_comprehensive(valid_config_file)

        # URL unreachability should not fail overall validation (it's a warning)
        assert "base_url" in result["sections"]
        assert result["sections"]["base_url"]["reachable"] is False

    def test_validate_config_comprehensive_report_structure(self, valid_config_file):
        """Test that comprehensive report has correct structure."""
        result = validate_config_comprehensive(valid_config_file)

        assert "overall_valid" in result
        assert "sections" in result
        assert isinstance(result["sections"], dict)

        # Check expected sections exist
        expected_sections = ["syntax", "required_fields", "base_url", "warnings"]
        for section in expected_sections:
            assert section in result["sections"]
