"""
Base class for listing discovery strategies.

This module provides the abstract base class that all listing strategies inherit from.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator, List


class ListingStrategy(ABC):
    """
    Abstract base class for listing discovery strategies.

    Each strategy implements a different method for discovering
    article URLs from a newspaper website.
    """

    def __init__(self, config: Dict[str, Any], max_pages: Optional[int] = None):
        """
        Initialize the strategy with configuration.

        Args:
            config: Strategy-specific configuration dictionary
            max_pages: Optional limit on the number of pages to discover
        """
        self.config = config
        self.max_pages = max_pages

    @abstractmethod
    async def discover_and_scrape(
        self, client, base_url: str, thumbnail_selector: str
    ) -> AsyncGenerator[List[Any], None]:
        """Discover listing pages and immediately scrape thumbnails."""
        pass
