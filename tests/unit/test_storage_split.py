"""Tests for storage package split."""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_storage_imports_after_split():
    """Test that CSVStorage still works after split."""
    from text.scrapers.pipelines.storage import CSVStorage

    storage = CSVStorage()
    assert storage is not None
    assert hasattr(storage, "csv_writer")
    assert hasattr(storage, "metadata_handler")
    assert hasattr(storage, "url_tracker")


def test_csv_format_unchanged():
    """Test that CSV output format is unchanged."""
    from text.scrapers.pipelines.storage import CSVStorage
    from text.scrapers.models import ArticleRecord

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        # Create test article
        article = ArticleRecord(
            url="https://example.com/article",
            title="Test Article",
            body="Test body content",
            date="2026-01-22",
            country="test",
            newspaper="test_paper",
            source="Test Paper",
            language="en",
            tags=["test", "article"],
        )

        # Save to CSV
        csv_path = storage.save_articles([article], "test", "test_paper")

        # Verify CSV format (check headers and content)
        assert csv_path.exists()
        content = csv_path.read_text()

        # Verify headers are in expected order
        lines = content.strip().split("\n")
        headers = lines[0]
        assert headers == "url,title,date,body,tags,source,country,language,_scraped_at"

        # Verify data row exists
        assert len(lines) >= 2
        assert "https://example.com/article" in lines[1]
        assert "Test Article" in lines[1]
        assert "test,article" in lines[1]  # tags joined by comma


def test_streaming_csv_format():
    """Test that streaming CSV writes maintain format."""
    from text.scrapers.pipelines.storage import CSVStorage
    from text.scrapers.models import ArticleRecord

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        # Create test article
        article = ArticleRecord(
            url="https://example.com/streaming",
            title="Streaming Article",
            body="Streaming body",
            date="2026-01-22",
            country="test",
            newspaper="test_paper",
            source="Test Paper",
            language="en",
        )

        # Initialize CSV
        csv_path = storage.initialize_csv("test", "test_paper")

        # Append article
        result_path = storage.append_article(article, "test", "test_paper")

        assert csv_path == result_path
        content = csv_path.read_text()

        # Verify headers
        lines = content.strip().split("\n")
        assert (
            lines[0] == "url,title,date,body,tags,source,country,language,_scraped_at"
        )

        # Verify data
        assert "https://example.com/streaming" in lines[1]


def test_metadata_format_unchanged():
    """Test that metadata.json format is unchanged."""
    from text.scrapers.pipelines.storage import CSVStorage
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        # Create test results
        results = {
            "success": True,
            "statistics": {"articles_scraped": 10, "urls_found": 15},
            "errors": [],
            "client_type": "playwright",
        }

        # Save metadata
        metadata_path = storage.save_metadata(results, "test", "test_paper")

        # Verify metadata structure
        assert metadata_path.exists()
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        assert metadata["newspaper"] == "test_paper"
        assert metadata["country"] == "test"
        assert metadata["success"] is True
        assert "scraped_at" in metadata
        assert metadata["statistics"]["articles_scraped"] == 10


def test_urls_csv_format():
    """Test that urls.csv format is unchanged."""
    from text.scrapers.pipelines.storage import CSVStorage
    from text.scrapers.models import ThumbnailRecord

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        # Create test thumbnails
        thumbnails = [
            ThumbnailRecord(
                url="https://example.com/article1", title="Article 1", date="2026-01-22"
            ),
            ThumbnailRecord(
                url="https://example.com/article2", title="Article 2", date="2026-01-21"
            ),
        ]

        # Save to urls.csv
        urls_path = storage.save_thumbnails_as_urls(thumbnails, "test", "test_paper")

        # Verify format
        assert urls_path.exists()
        content = urls_path.read_text()
        lines = content.strip().split("\n")

        # Check headers
        assert lines[0] == "url,title,date"

        # Check data
        assert len(lines) == 3  # header + 2 data rows
        assert "https://example.com/article1" in content


def test_failed_urls_format():
    """Test that failed URLs CSV format is unchanged."""
    from text.scrapers.pipelines.storage import CSVStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        failed_urls = [
            {"url": "https://example.com/failed1", "status_code": 404},
            {"url": "https://example.com/failed2", "status_code": 500},
        ]

        # Save failed URLs
        failed_path = storage.save_failed_urls(failed_urls, "test", "test_paper")

        assert failed_path is not None
        assert failed_path.exists()
        assert "failed" in str(failed_path)


def test_backwards_compatibility():
    """Test that all existing methods are still accessible."""
    from text.scrapers.pipelines.storage import CSVStorage

    storage = CSVStorage()

    # Verify all public methods exist
    assert hasattr(storage, "save_articles")
    assert hasattr(storage, "append_article")
    assert hasattr(storage, "initialize_csv")
    assert hasattr(storage, "save_metadata")
    assert hasattr(storage, "save_thumbnails_as_urls")
    assert hasattr(storage, "save_failed_urls")
    assert hasattr(storage, "save_failed_news")
    assert hasattr(storage, "load_urls_from_csv")
    assert hasattr(storage, "load_existing_articles")
    assert hasattr(storage, "get_existing_urls")
    assert hasattr(storage, "get_existing_article_urls")
    assert hasattr(storage, "append_thumbnails_to_urls")
    assert hasattr(storage, "ensure_urls_csv_from_news")
    assert hasattr(storage, "get_newspaper_dir")


def test_sub_modules_exist():
    """Test that storage sub-modules exist."""
    from text.scrapers.pipelines import storage

    # Check that sub-modules exist as attributes
    assert hasattr(storage, "CSVStorage")
    # The internal modules shouldn't be directly exposed
    # but CSVStorage should use them internally


def test_directory_management():
    """Test directory creation and sanitization."""
    from text.scrapers.pipelines.storage import CSVStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = CSVStorage(tmpdir)

        # Test directory creation
        newspaper_dir = storage.get_newspaper_dir("Test Country", "Test-Paper!")

        # Should sanitize names
        assert "test_country" in str(newspaper_dir).lower()
        assert (
            "test-paper" in str(newspaper_dir).lower()
            or "test_paper" in str(newspaper_dir).lower()
        )
