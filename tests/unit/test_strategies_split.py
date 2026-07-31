"""
Tests for the listing_strategies.py split refactoring.

This test suite verifies that the split refactoring maintains backwards compatibility
and all imports work correctly.
"""


def test_strategy_imports_work_after_split():
    """Test that all strategies can be imported from the new package."""
    from text.scrapers.strategies import (
        ListingStrategy,
        PaginationStrategy,
        ArchiveStrategy,
        PaginatedArchiveStrategy,
        ApiStrategy,
        FollowLinkStrategy,
    )

    # Verify all classes are importable
    assert ListingStrategy is not None
    assert PaginationStrategy is not None
    assert ArchiveStrategy is not None
    assert PaginatedArchiveStrategy is not None
    assert ApiStrategy is not None
    assert FollowLinkStrategy is not None

    # Verify they have the expected methods
    assert hasattr(ListingStrategy, "__init__")
    assert hasattr(ListingStrategy, "discover_and_scrape")
    assert hasattr(PaginationStrategy, "generate_page_urls")


def test_create_strategy_factory_works():
    """Test that the factory function creates the correct strategy instances."""
    from text.scrapers.strategies import create_listing_strategy

    # Test pagination strategy
    pagination_config = {
        "type": "pagination",
        "url_template": "https://example.com/page/{num}",
        "start_page": 1,
    }
    strategy = create_listing_strategy(pagination_config)
    from text.scrapers.strategies import PaginationStrategy

    assert isinstance(strategy, PaginationStrategy)

    # Test archive strategy
    archive_config = {
        "type": "archive",
        "url_template": "https://example.com/{year}/{month}/",
        "start_date": "2025-01-01",
        "date_format": "monthly",
    }
    strategy = create_listing_strategy(archive_config)
    from text.scrapers.strategies import ArchiveStrategy

    assert isinstance(strategy, ArchiveStrategy)

    # Test API strategy
    api_config = {
        "type": "api",
        "url_template": "https://api.example.com/articles?page={page}",
        "pagination_type": "page",
    }
    strategy = create_listing_strategy(api_config)
    from text.scrapers.strategies import ApiStrategy

    assert isinstance(strategy, ApiStrategy)

    # Test follow_link strategy
    follow_config = {
        "type": "follow_link",
        "start_url": "https://example.com/news",
        "follow_selector": "a.next::attr(href)",
    }
    strategy = create_listing_strategy(follow_config)
    from text.scrapers.strategies import FollowLinkStrategy

    assert isinstance(strategy, FollowLinkStrategy)

    # Test paginated_archive strategy
    paginated_archive_config = {
        "type": "paginated_archive",
        "start_url": "https://example.com/{year}/{month}/{day}/",
        "url_template": "https://example.com/{year}/{month}/{day}/page/{num}/",
        "start_date": "2025-01-01",
        "date_format": "daily",
    }
    strategy = create_listing_strategy(paginated_archive_config)
    from text.scrapers.strategies import PaginatedArchiveStrategy

    assert isinstance(strategy, PaginatedArchiveStrategy)


def test_rss_strategy_factory_and_in_feed_body():
    """RSS factory dispatch + in-feed body flattening of CDATA HTML."""
    from bs4 import BeautifulSoup
    from text.scrapers.strategies import create_listing_strategy, RssStrategy

    config = {
        "type": "rss",
        "feed_urls": ["https://example.com/feed/"],
        "page_param": "paged",
        "body_in_feed": True,
    }
    strategy = create_listing_strategy(config)
    assert isinstance(strategy, RssStrategy)
    assert strategy.body_in_feed is True

    feed = (
        '<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
        "<item><title>T</title><link>https://example.com/a</link>"
        "<content:encoded><![CDATA[<p>Hello <b>world</b></p>"
        "<p>Second line.</p>]]></content:encoded></item>"
        "<item><title>T</title><link>https://example.com/b</link>"
        "<description><![CDATA[<p>Just a teaser.</p>]]></description></item>"
        "<item><link>https://example.com/c</link></item>"
        "</channel></rss>"
    )
    items = BeautifulSoup(feed, "xml").select("item")

    # content:encoded (CDATA HTML) is flattened to text.
    assert strategy.extract_body(items[0]) == "Hello world Second line."
    # Falls back to description when content:encoded is absent.
    assert strategy.extract_body(items[1]) == "Just a teaser."
    # No body tags -> empty string (caller falls back to article page).
    assert strategy.extract_body(items[2]) == ""


def test_backwards_compatibility_removed():
    """Test that old deprecated imports have been removed."""
    import importlib

    import pytest

    # Verify that importing from old location raises ModuleNotFoundError
    with pytest.raises(ModuleNotFoundError, match="listing_strategies"):
        importlib.import_module("text.scrapers.listing_strategies")

    # Verify that the new imports work correctly
    from text.scrapers.strategies import (
        create_listing_strategy as new_create_listing_strategy,
        PaginationStrategy as NewPaginationStrategy,
    )

    assert new_create_listing_strategy is not None
    assert NewPaginationStrategy is not None
