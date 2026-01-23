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


def test_backwards_compatibility_import():
    """Test that old imports still work (with deprecation warning)."""
    import sys

    # Remove the module if already imported to ensure we capture the warning
    if "text.scrapers.listing_strategies" in sys.modules:
        del sys.modules["text.scrapers.listing_strategies"]

    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Import from old location
        from text.scrapers.listing_strategies import (
            create_listing_strategy,
            PaginationStrategy,
        )

        # Verify deprecation warning was raised
        assert len(w) >= 1, f"Expected at least 1 warning, got {len(w)}"
        # Find the deprecation warning
        deprecation_warnings = [
            warning for warning in w if issubclass(warning.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) >= 1, "No DeprecationWarning found"
        assert "deprecated" in str(deprecation_warnings[0].message).lower()

        # Verify the imports still work
        assert create_listing_strategy is not None
        assert PaginationStrategy is not None
