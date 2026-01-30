#!/usr/bin/env python3
"""
Test script to verify metrics initialization in NewspaperScraper.

Tests that ScraperMetrics is properly initialized when loading a real scraper config.
"""

import yaml
from datetime import datetime
from pathlib import Path
from src.text.scrapers.scraper import NewspaperScraper


def test_metrics_initialization():
    """Test that metrics are initialized when loading a scraper config."""

    # Load a real config file (fiji_sun)
    config_path = Path("src/text/scrapers/configs/fiji/fiji_sun.yaml")

    print(f"Loading config from: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    print(f"Config loaded: {config['name']} ({config['country']})")

    # Initialize the scraper
    scraper = NewspaperScraper(config)

    # Verify metrics are initialized
    assert hasattr(scraper, "metrics"), "Scraper should have metrics attribute"
    assert scraper.metrics is not None, "Metrics should not be None"

    # Verify metrics properties
    assert (
        scraper.metrics.newspaper == scraper.name
    ), f"Expected newspaper={scraper.name}, got {scraper.metrics.newspaper}"
    assert (
        scraper.metrics.country == scraper.country
    ), f"Expected country={scraper.country}, got {scraper.metrics.country}"
    assert (
        scraper.metrics.mode == "update"
    ), f"Expected mode='update', got {scraper.metrics.mode}"
    assert isinstance(
        scraper.metrics.started_at, datetime
    ), "started_at should be a datetime object"

    # Verify started_at is recent (within last 5 seconds)
    now = datetime.utcnow()
    time_diff = (now - scraper.metrics.started_at).total_seconds()
    assert (
        time_diff < 5
    ), f"started_at should be recent, but was {time_diff} seconds ago"

    print("\n✓ All checks passed!")
    print(f"  - Newspaper: {scraper.metrics.newspaper}")
    print(f"  - Country: {scraper.metrics.country}")
    print(f"  - Mode: {scraper.metrics.mode}")
    print(f"  - Started at: {scraper.metrics.started_at}")

    return True


if __name__ == "__main__":
    try:
        test_metrics_initialization()
        print("\n✅ Test PASSED: Metrics initialization works correctly")
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
