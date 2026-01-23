"""
DEPRECATED: Migrated to strategies/ package.

Import from text.scrapers.strategies instead.

This file is kept for backwards compatibility only.
All listing strategies have been moved to the strategies package:
- text.scrapers.strategies.base.ListingStrategy
- text.scrapers.strategies.pagination.PaginationStrategy
- text.scrapers.strategies.archive.ArchiveStrategy
- text.scrapers.strategies.archive.PaginatedArchiveStrategy
- text.scrapers.strategies.api.ApiStrategy
- text.scrapers.strategies.follow_link.FollowLinkStrategy
"""

import warnings

warnings.warn(
    "listing_strategies.py is deprecated. Import from text.scrapers.strategies instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backwards compatibility
from .strategies import (  # noqa: E402
    ApiStrategy,
    ArchiveStrategy,
    FollowLinkStrategy,
    ListingStrategy,
    PaginatedArchiveStrategy,
    PaginationStrategy,
    create_listing_strategy,
)

__all__ = [
    "ListingStrategy",
    "PaginationStrategy",
    "ArchiveStrategy",
    "PaginatedArchiveStrategy",
    "ApiStrategy",
    "FollowLinkStrategy",
    "create_listing_strategy",
]
