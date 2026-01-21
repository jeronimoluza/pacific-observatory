"""
Pytest configuration and fixtures for the text module tests.

Provides:
- HTTP mocking infrastructure using pytest-httpx
- Sample HTML/JSON fixtures from tests/fixtures/
- Test configurations and data factories
- Database fixtures for run tracker tests

Usage:
    # In test files:
    def test_scraper(mock_http, sample_listing_html):
        mock_http.add_response(url=..., html=sample_listing_html)
        ...
"""

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any

import pytest

# Add project root to path BEFORE importing local modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Now safe to import local modules
from text.core.events import EventEmitter  # noqa: E402
from text.core.logging_config import configure_logging  # noqa: E402
from text.core.run_tracker import RunTracker  # noqa: E402


# =============================================================================
# Directory Constants
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HTML_FIXTURES_DIR = FIXTURES_DIR / "html"
JSON_FIXTURES_DIR = FIXTURES_DIR / "json"
CONFIG_FIXTURES_DIR = FIXTURES_DIR / "configs"
TEST_DATA_DIR = Path(__file__).parent / "data"


# =============================================================================
# Session-scoped Setup
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure logging for tests with minimal output."""
    configure_logging(log_level="WARNING", enable_file=False)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return FIXTURES_DIR


# =============================================================================
# HTML Fixtures
# =============================================================================


@pytest.fixture
def sample_listing_html() -> str:
    """Load the pagination listing HTML fixture."""
    return (HTML_FIXTURES_DIR / "pagination_listing.html").read_text()


@pytest.fixture
def sample_article_html() -> str:
    """Load the standard article HTML fixture."""
    return (HTML_FIXTURES_DIR / "article_standard.html").read_text()


@pytest.fixture
def sample_archive_html() -> str:
    """Load the archive listing HTML fixture."""
    return (HTML_FIXTURES_DIR / "archive_listing.html").read_text()


@pytest.fixture
def sample_paywall_html() -> str:
    """Load the paywall article HTML fixture."""
    return (HTML_FIXTURES_DIR / "article_paywall.html").read_text()


@pytest.fixture
def sample_error_html() -> str:
    """Load the 404 error page HTML fixture."""
    return (HTML_FIXTURES_DIR / "error_404.html").read_text()


# =============================================================================
# JSON Fixtures
# =============================================================================


@pytest.fixture
def sample_api_response() -> Dict[str, Any]:
    """Load the API response JSON fixture."""
    return json.loads((JSON_FIXTURES_DIR / "api_response.json").read_text())


@pytest.fixture
def sample_api_error() -> Dict[str, Any]:
    """Load the API error JSON fixture."""
    return json.loads((JSON_FIXTURES_DIR / "api_error.json").read_text())


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Load the test newspaper configuration."""
    import yaml

    return yaml.safe_load((CONFIG_FIXTURES_DIR / "test_newspaper.yaml").read_text())


@pytest.fixture
def minimal_config() -> Dict[str, Any]:
    """Return a minimal configuration for testing."""
    return {
        "name": "test_newspaper",
        "country": "test_country",
        "language": "en",
        "base_url": "https://test.example.com",
        "client": "http",
        "listing": {
            "type": "pagination",
            "start_url": "/news",
            "page_param": "page",
        },
        "thumbnails": {
            "container": "article",
            "title": "h2",
            "link": "a",
        },
        "article": {
            "title": "h1",
            "body": "div.content",
        },
    }


# =============================================================================
# HTTP Mocking Fixtures (pytest-httpx)
# =============================================================================


@pytest.fixture
def mock_http(httpx_mock):
    """
    Provide the httpx mock for HTTP request mocking.

    This is a wrapper around pytest-httpx's httpx_mock fixture.

    Usage:
        def test_fetch(mock_http, sample_article_html):
            mock_http.add_response(
                url="https://example.com/article",
                html=sample_article_html,
            )
            # ... test code ...
    """
    return httpx_mock


@pytest.fixture
def mock_newspaper_http(httpx_mock, sample_listing_html, sample_article_html):
    """
    Pre-configured mock with common newspaper HTTP patterns.

    Mocks:
    - Listing pages at /news?page=N
    - Article pages at /news/*
    """
    # Mock listing pages
    httpx_mock.add_response(
        url=re.compile(r".*example\.com/news\?page=\d+"),
        html=sample_listing_html,
    )

    # Mock article pages
    httpx_mock.add_response(
        url=re.compile(r".*example\.com/news/\d+/\d+/.*"),
        html=sample_article_html,
    )

    return httpx_mock


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def run_tracker(temp_db) -> RunTracker:
    """Create a run tracker with a temporary database."""
    return RunTracker(db_path=temp_db)


@pytest.fixture
def event_emitter() -> EventEmitter:
    """Create a fresh event emitter for testing."""
    return EventEmitter()


# =============================================================================
# Data Directory Fixtures
# =============================================================================


@pytest.fixture
def test_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory for test outputs."""
    import shutil

    data_dir = TEST_DATA_DIR / "temp"
    data_dir.mkdir(parents=True, exist_ok=True)

    yield data_dir

    # Cleanup
    if data_dir.exists():
        shutil.rmtree(data_dir)


# =============================================================================
# Factory Fixtures
# =============================================================================


@pytest.fixture
def thumbnail_factory():
    """Factory for creating ThumbnailRecord test data."""
    from text.scrapers.models import ThumbnailRecord

    def _create(
        url: str = "https://example.com/article/1",
        title: str = "Test Article",
        date: str = "2024-01-15",
        **kwargs,
    ) -> ThumbnailRecord:
        return ThumbnailRecord(
            url=url,
            title=title,
            date=date,
            **kwargs,
        )

    return _create


@pytest.fixture
def article_factory():
    """Factory for creating ArticleRecord test data."""
    from text.scrapers.models import ArticleRecord

    def _create(
        url: str = "https://example.com/article/1",
        title: str = "Test Article",
        body: str = "This is the article body content.",
        date: str = "2024-01-15",
        **kwargs,
    ) -> ArticleRecord:
        return ArticleRecord(
            url=url,
            title=title,
            body=body,
            date=date,
            **kwargs,
        )

    return _create


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (no network, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (may require network)"
    )
    config.addinivalue_line("markers", "slow: Tests that take more than 10 seconds")


def pytest_collection_modifyitems(config, items):
    """
    Auto-mark tests based on their location.

    - tests/unit/*.py -> @pytest.mark.unit
    - tests/integration/*.py -> @pytest.mark.integration
    """
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
