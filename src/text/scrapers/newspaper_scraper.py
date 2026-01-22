"""
Generic newspaper scraper driven by configuration.

This module provides a NewspaperScraper class that can scrape any newspaper
based on a configuration dictionary, using the appropriate client and strategy.

DEPRECATED: This file is being migrated to scraper.py, discovery.py, extraction.py, and modes.py.

DO NOT ADD NEW CODE HERE. This file will be removed after migration is complete.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "newspaper_scraper.py is deprecated. Import from text.scrapers.scraper instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backwards compatibility during migration
from .scraper import NewspaperScraper  # noqa: E402

__all__ = ["NewspaperScraper"]

# ============================================================================
# ORIGINAL CODE REMOVED
# The implementation has been moved to scraper.py, discovery.py, and extraction.py
# ============================================================================

# The following code has been removed and replaced with the re-export above.
# All functionality is now available through:
# - scraper.py: NewspaperScraper class
# - discovery.py: DiscoveryOrchestrator
# - extraction.py: ExtractionOrchestrator
# - modes.py: ScrapeMode enum
