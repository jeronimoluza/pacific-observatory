"""
Refactored newspaper scraping framework.

This package has been decomposed into specialized modules following
the config-driven architecture specified in the PRD.

Core modules:
- client_http.py: AsyncHttpClient for high-performance async HTTP scraping
- newspaper_scraper.py: NewspaperScraper orchestrator
- models.py: Pydantic data models
- listing_strategies.py: Listing discovery strategies
- factory.py: Factory functions for creating scrapers from config
- pipelines/: Data processing and storage
- orchestration/: Scripts for running scrapers

For backward compatibility, you can still import the main classes:
"""

# Import main classes for backward compatibility
from .client_http import AsyncHttpClient
from .newspaper_scraper import NewspaperScraper
from .models import ThumbnailRecord, ArticleRecord, NewspaperConfig
from .factory import create_scraper, create_scraper_from_file
from .pipelines.storage import CSVStorage

# Legacy alias for backward compatibility
RequestsScraper = AsyncHttpClient  # Note: This is now async

__all__ = [
    'AsyncHttpClient',
    'NewspaperScraper',
    'ThumbnailRecord',
    'ArticleRecord',
    'NewspaperConfig',
    'create_scraper',
    'create_scraper_from_file',
    'CSVStorage',
    # Legacy alias
    'RequestsScraper',
]