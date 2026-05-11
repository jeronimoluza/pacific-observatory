"""
Listing discovery strategies package.

This package contains different strategies for discovering article listings
from newspaper websites, including pagination, archives, categories, and search.
"""

from typing import Dict, Any, Optional

from .base import ListingStrategy
from .pagination import PaginationStrategy
from .archive import ArchiveStrategy, PaginatedArchiveStrategy
from .api import ApiStrategy
from .follow_link import FollowLinkStrategy
from .cursor import CursorStrategy
from .sitemap import SitemapStrategy

__all__ = [
    "ListingStrategy",
    "PaginationStrategy",
    "ArchiveStrategy",
    "PaginatedArchiveStrategy",
    "ApiStrategy",
    "FollowLinkStrategy",
    "CursorStrategy",
    "SitemapStrategy",
    "create_listing_strategy",
]


def create_listing_strategy(
    config: Dict[str, Any], max_pages: Optional[int] = None
) -> ListingStrategy:
    """
    Factory function to create a listing strategy based on configuration.

    Args:
        config: Strategy configuration dictionary
        max_pages: Optional limit on the number of pages to discover

    Returns:
        Appropriate ListingStrategy instance

    Raises:
        ValueError: If strategy type is unknown
    """
    strategy_type = config.get("type")

    if strategy_type == "pagination":
        return PaginationStrategy(config, max_pages=max_pages)
    elif strategy_type == "archive":
        return ArchiveStrategy(config, max_pages=max_pages)
    elif strategy_type == "paginated_archive":
        return PaginatedArchiveStrategy(config, max_pages=max_pages)
    elif strategy_type == "api":
        return ApiStrategy(config, max_pages=max_pages)
    elif strategy_type == "follow_link":
        return FollowLinkStrategy(config, max_pages=max_pages)
    elif strategy_type == "cursor":
        return CursorStrategy(config, max_pages=max_pages)
    elif strategy_type == "sitemap":
        return SitemapStrategy(config, max_pages=max_pages)
    else:
        raise ValueError(f"Unknown listing strategy type: {strategy_type}")
