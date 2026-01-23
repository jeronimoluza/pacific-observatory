"""
Storage pipeline for scraped data.

Organizes data in CSV format by country/newspaper.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Union, List, Dict, Any, Optional

from .csv_writer import CSVWriter
from .metadata import MetadataHandler
from .urls import URLTracker
from ...models import ArticleRecord, ThumbnailRecord


class CSVStorage:
    """
    Main storage orchestrator for scraped data.

    Delegates to specialized handlers:
    - CSVWriter: Article CSV operations
    - MetadataHandler: Metadata JSON operations
    - URLTracker: URL tracking and failed URL logging
    """

    def __init__(self, base_data_dir: Union[str, Path] = None):
        """
        Initialize the storage system.

        Args:
            base_data_dir: Base directory for data storage
        """
        if base_data_dir is None:
            # Use environment variable or default
            base_data_dir = os.environ.get("DATA_FOLDER_PATH", "./data/text")

        self.base_data_dir = Path(base_data_dir)
        self.ensure_directories()

        # Delegate to focused handlers
        self.csv_writer = CSVWriter(self.base_data_dir)
        self.metadata_handler = MetadataHandler(self.base_data_dir)
        self.url_tracker = URLTracker(self.base_data_dir)

        # Streaming state tracking (kept here for now)
        self._streaming_file_handles: Dict[str, Any] = {}
        self._streaming_headers_written: Dict[str, bool] = {}

    def ensure_directories(self):
        """Ensure the base directory structure exists."""
        # Only create the processed directory - others are created as needed
        processed_dir = self.base_data_dir
        processed_dir.mkdir(parents=True, exist_ok=True)

    def get_newspaper_dir(self, country: str, newspaper: str) -> Path:
        """
        Get the directory path for a specific newspaper.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            Path to the newspaper's data directory
        """
        # Sanitize names for filesystem
        country = self._sanitize_name(country)
        newspaper = self._sanitize_name(newspaper)

        return self.base_data_dir / country / newspaper

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in filesystem paths.

        Args:
            name: Name to sanitize

        Returns:
            Sanitized name safe for filesystem use
        """
        # Replace spaces with underscores and remove special characters
        sanitized = re.sub(r"[^\w\-_.]", "_", name.replace(" ", "_").lower())
        return sanitized.strip("_")

    def _get_streaming_key(self, country: str, newspaper: str) -> str:
        """Get a unique key for streaming state tracking."""
        country = self._sanitize_name(country)
        newspaper = self._sanitize_name(newspaper)
        return f"{country}/{newspaper}"

    # CSV Writer delegations

    def initialize_csv(
        self,
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Path:
        """
        Initialize CSV file with headers for streaming writes.

        Args:
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the initialized CSV file
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        csv_path = self.csv_writer.initialize_csv(newspaper_dir, timestamp)

        # Track that headers have been written
        key = self._get_streaming_key(country, newspaper)
        self._streaming_headers_written[key] = True

        return csv_path

    def append_article(
        self,
        article: ArticleRecord,
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Path:
        """
        Append a single article to the CSV file (streaming write).

        Args:
            article: ArticleRecord object to append
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the CSV file
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.csv_writer.append_article(article, newspaper_dir, timestamp)

    def save_articles(
        self,
        articles: List[ArticleRecord],
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Path:
        """
        Save article records to CSV file.

        Args:
            articles: List of ArticleRecord objects
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.csv_writer.save_articles(articles, newspaper_dir, timestamp)

    def load_existing_articles(
        self, country: str, newspaper: str
    ) -> Optional[List[ArticleRecord]]:
        """
        Load existing articles from news.csv file.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            List of ArticleRecord objects if file exists, None otherwise
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.csv_writer.load_existing_articles(newspaper_dir)

    def get_existing_article_urls(self, country: str, newspaper: str) -> set:
        """
        Get set of existing article URLs from news.csv file.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            Set of existing article URLs
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.csv_writer.get_existing_article_urls(newspaper_dir)

    # Metadata Handler delegations

    def serialize_for_json(self, obj: Any) -> Any:
        """
        Recursively serialize objects to ensure JSON compatibility.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable version of the object
        """
        return self.metadata_handler.serialize_for_json(obj)

    def save_metadata(
        self,
        results: Dict[str, Any],
        country: str,
        newspaper: str,
        timestamp: datetime = None,
        metadata_type: str = "news",
    ) -> Path:
        """
        Save scraping metadata and statistics.

        Args:
            results: Scraping results dictionary
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for filename
            metadata_type: Type of metadata ("urls" or "news")

        Returns:
            Path to the saved metadata file
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.metadata_handler.save_metadata(
            results, newspaper_dir, country, newspaper, timestamp, metadata_type
        )

    # URL Tracker delegations

    def save_thumbnails_as_urls(
        self,
        thumbnails: List[ThumbnailRecord],
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save thumbnails to urls.csv file.

        Args:
            thumbnails: List of ThumbnailRecord objects
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the saved file, or None if no thumbnails
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.save_thumbnails_as_urls(
            thumbnails, newspaper_dir, timestamp
        )

    def load_urls_from_csv(
        self, country: str, newspaper: str
    ) -> Optional[List[ThumbnailRecord]]:
        """
        Load thumbnail URLs from urls.csv file.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            List of ThumbnailRecord objects if file exists, None otherwise
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.load_urls_from_csv(newspaper_dir)

    def get_existing_urls(self, country: str, newspaper: str) -> set:
        """
        Load existing URLs from urls.csv for stopping rule checks.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            Set of existing URL strings, empty set if file doesn't exist
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.get_existing_urls(newspaper_dir)

    def append_thumbnails_to_urls(
        self,
        thumbnails: List[ThumbnailRecord],
        country: str,
        newspaper: str,
    ) -> Optional[Path]:
        """
        Append new thumbnails to existing urls.csv with deduplication.

        Args:
            thumbnails: List of ThumbnailRecord objects to append
            country: Country code
            newspaper: Newspaper name

        Returns:
            Path to the urls.csv file, or None if no thumbnails provided
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.append_thumbnails_to_urls(thumbnails, newspaper_dir)

    def ensure_urls_csv_from_news(self, country: str, newspaper: str) -> bool:
        """
        Create urls.csv from news.csv if urls.csv does NOT exist.

        Args:
            country: Country code
            newspaper: Newspaper name

        Returns:
            True if urls.csv was created, False if it already existed or news.csv doesn't exist
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        news_path = newspaper_dir / "news.csv"
        return self.url_tracker.ensure_urls_csv_from_news(newspaper_dir, news_path)

    def save_failed_urls(
        self,
        failed_urls: List[Dict[str, Any]],
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save failed URLs to CSV file in failed subdirectory.

        Args:
            failed_urls: List of failed URL dictionaries with url and status_code
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file, or None if no failed URLs
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.save_failed_urls(failed_urls, newspaper_dir, timestamp)

    def save_failed_news(
        self,
        failed_news: List[Dict[str, Any]],
        country: str,
        newspaper: str,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save failed news articles to CSV file in failed subdirectory.

        Args:
            failed_news: List of failed news dictionaries with url and status_code
            country: Country code
            newspaper: Newspaper name
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file, or None if no failed news
        """
        newspaper_dir = self.get_newspaper_dir(country, newspaper)
        return self.url_tracker.save_failed_news(failed_news, newspaper_dir, timestamp)


# Re-export for convenience
__all__ = ["CSVStorage"]
