"""
Tests for the newspaper_scraper.py split refactoring.

This test suite verifies that the split refactoring maintains backwards compatibility
and all imports work correctly.
"""


def test_scraper_imports_work_after_split():
    """Test that NewspaperScraper can be imported from new location."""
    from text.scrapers.scraper import NewspaperScraper

    assert NewspaperScraper is not None
    assert hasattr(NewspaperScraper, "__init__")


def test_scrape_mode_enum_exists():
    """Test that ScrapeMode enum exists with all 4 modes."""
    from text.scrapers.modes import ScrapeMode

    assert hasattr(ScrapeMode, "UPDATE")
    assert hasattr(ScrapeMode, "RESUME")
    assert hasattr(ScrapeMode, "FULL_DISCOVERY")
    assert hasattr(ScrapeMode, "FULL_FROM_SCRATCH")


def test_scraper_initialization_unchanged(minimal_config):
    """Test that NewspaperScraper initialization works as before."""
    from text.scrapers.scraper import NewspaperScraper

    scraper = NewspaperScraper(minimal_config)

    # Verify basic attributes are set correctly
    assert scraper.name == "test_newspaper"
    assert scraper.country == "test_country"
    assert scraper.base_url == "https://test.example.com/"
    assert scraper.language == "en"

    # Verify orchestrators are created
    assert hasattr(scraper, "discovery_orchestrator")
    assert hasattr(scraper, "extraction_orchestrator")

    # Verify original data structures exist
    assert hasattr(scraper, "scraped_thumbnails")
    assert hasattr(scraper, "scraped_articles")
    assert hasattr(scraper, "failed_urls")
    assert hasattr(scraper, "failed_news")
