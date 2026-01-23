"""
URL tracking operations for scraped data.

Manages urls.csv and failed URLs tracking.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ...models import ThumbnailRecord

logger = logging.getLogger(__name__)


class URLTracker:
    """Handles URL tracking and failed URL logging."""

    def __init__(self, base_data_dir: Path):
        """
        Initialize URL tracker.

        Args:
            base_data_dir: Base directory for data storage
        """
        self.base_data_dir = base_data_dir

    def save_thumbnails_as_urls(
        self,
        thumbnails: List[ThumbnailRecord],
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save thumbnails to urls.csv file.

        Args:
            thumbnails: List of ThumbnailRecord objects
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the saved file, or None if no thumbnails
        """
        import pandas as pd

        if not thumbnails:
            return None

        if timestamp is None:
            timestamp = datetime.now()

        # Create directory
        newspaper_dir.mkdir(parents=True, exist_ok=True)

        # Save as urls.csv
        filename = "urls.csv"
        file_path = newspaper_dir / filename

        # Convert thumbnails to dictionaries
        data = []
        for thumbnail in thumbnails:
            thumb_data = {
                "url": str(thumbnail.url),
                "title": thumbnail.title,
                "date": thumbnail.date,
            }
            data.append(thumb_data)

        # Create DataFrame and save to CSV
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False, encoding="utf-8")

        logger.info(f"Saved {len(thumbnails)} thumbnails to {file_path}")
        return file_path

    def load_urls_from_csv(
        self, newspaper_dir: Path
    ) -> Optional[List[ThumbnailRecord]]:
        """
        Load thumbnail URLs from urls.csv file.

        Args:
            newspaper_dir: Directory for the newspaper

        Returns:
            List of ThumbnailRecord objects if file exists, None otherwise
        """
        import pandas as pd

        # Check for urls.csv file
        filename = "urls.csv"
        file_path = newspaper_dir / filename

        if not file_path.exists():
            logger.warning(f"No URLs file found: {file_path}")
            return None

        try:
            # Read CSV file
            df = pd.read_csv(file_path, encoding="utf-8")
            thumbnails = []

            for _, row in df.iterrows():
                try:
                    # Convert row to dictionary
                    thumb_data = row.to_dict()

                    # Handle NaN values
                    thumb_data = {
                        k: v if pd.notna(v) else None for k, v in thumb_data.items()
                    }

                    thumbnail = ThumbnailRecord(**thumb_data)
                    thumbnails.append(thumbnail)
                except Exception as row_error:
                    logger.warning(
                        f"Failed to parse thumbnail row in {file_path}: {row_error}"
                    )
                    continue

            logger.info(f"Loaded {len(thumbnails)} thumbnails from {file_path}")
            return thumbnails

        except Exception as e:
            logger.error(f"Failed to load URLs from {file_path}: {e}")
            return None

    def get_existing_urls(self, newspaper_dir: Path) -> set:
        """
        Load existing URLs from urls.csv for stopping rule checks.

        Args:
            newspaper_dir: Directory for the newspaper

        Returns:
            Set of existing URL strings, empty set if file doesn't exist
        """
        import pandas as pd

        # Check for urls.csv file
        filename = "urls.csv"
        file_path = newspaper_dir / filename

        if not file_path.exists():
            logger.info(f"No urls.csv file found: {file_path}")
            return set()

        try:
            # Read CSV file and extract URLs
            df = pd.read_csv(file_path, encoding="utf-8")
            urls = set(df["url"].astype(str).unique())
            logger.info(f"Loaded {len(urls)} existing URLs from urls.csv")
            return urls

        except Exception as e:
            logger.error(f"Failed to get existing URLs from {file_path}: {e}")
            return set()

    def append_thumbnails_to_urls(
        self,
        thumbnails: List[ThumbnailRecord],
        newspaper_dir: Path,
    ) -> Optional[Path]:
        """
        Append new thumbnails to existing urls.csv with deduplication.

        Args:
            thumbnails: List of ThumbnailRecord objects to append
            newspaper_dir: Directory for the newspaper

        Returns:
            Path to the urls.csv file, or None if no thumbnails provided
        """
        import pandas as pd

        if not thumbnails:
            return None

        # Create directory if needed
        newspaper_dir.mkdir(parents=True, exist_ok=True)

        # File path
        filename = "urls.csv"
        file_path = newspaper_dir / filename

        # Convert new thumbnails to DataFrame
        new_data = []
        for thumbnail in thumbnails:
            thumb_data = {
                "url": str(thumbnail.url),
                "title": thumbnail.title,
                "date": thumbnail.date,
            }
            new_data.append(thumb_data)
        new_df = pd.DataFrame(new_data)

        # Load existing data if file exists
        if file_path.exists():
            try:
                existing_df = pd.read_csv(file_path, encoding="utf-8")
                # Merge and deduplicate by URL (keep last occurrence to update old entries)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=["url"], keep="last")
                logger.info(
                    f"Merged {len(new_df)} new URLs with {len(existing_df)} existing. "
                    f"Total after dedup: {len(combined_df)}"
                )
            except Exception as e:
                logger.warning(f"Failed to load existing urls.csv, overwriting: {e}")
                combined_df = new_df
        else:
            combined_df = new_df
            logger.info(f"Creating new urls.csv with {len(combined_df)} URLs")

        # Save to CSV
        combined_df.to_csv(file_path, index=False, encoding="utf-8")
        logger.info(f"Saved {len(combined_df)} URLs to {file_path}")

        return file_path

    def ensure_urls_csv_from_news(self, newspaper_dir: Path, news_path: Path) -> bool:
        """
        Create urls.csv from news.csv if urls.csv does NOT exist.

        IMPORTANT: Only creates urls.csv if it does not already exist.
        Never overwrites existing urls.csv to preserve pending URLs.

        Args:
            newspaper_dir: Directory for the newspaper
            news_path: Path to news.csv file

        Returns:
            True if urls.csv was created, False if it already existed or news.csv doesn't exist
        """
        import pandas as pd

        urls_path = newspaper_dir / "urls.csv"

        # If urls.csv already exists, do nothing
        if urls_path.exists():
            logger.info(f"urls.csv already exists: {urls_path}")
            return False

        # If news.csv doesn't exist, nothing to create from
        if not news_path.exists():
            logger.info(f"No news.csv to create urls.csv from: {news_path}")
            return False

        try:
            # Read news.csv and extract url, title, date columns
            news_df = pd.read_csv(news_path, encoding="utf-8")

            # Check required columns exist
            required_cols = ["url", "title", "date"]
            missing_cols = [col for col in required_cols if col not in news_df.columns]
            if missing_cols:
                logger.error(f"news.csv missing required columns: {missing_cols}")
                return False

            # Extract only the columns needed for urls.csv
            urls_df = news_df[["url", "title", "date"]].copy()

            # Deduplicate by URL
            urls_df = urls_df.drop_duplicates(subset=["url"], keep="first")

            # Ensure directory exists
            newspaper_dir.mkdir(parents=True, exist_ok=True)

            # Save to urls.csv
            urls_df.to_csv(urls_path, index=False, encoding="utf-8")
            logger.info(
                f"Created urls.csv from news.csv with {len(urls_df)} URLs: {urls_path}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to create urls.csv from news.csv: {e}")
            return False

    def save_failed_urls(
        self,
        failed_urls: List[Dict[str, Any]],
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save failed URLs to CSV file in failed subdirectory.

        Args:
            failed_urls: List of failed URL dictionaries with url and status_code
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file, or None if no failed URLs
        """
        import pandas as pd

        if not failed_urls:
            return None

        if timestamp is None:
            timestamp = datetime.now()

        # Create directory
        failed_dir = newspaper_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        filename = f"failed_urls_{timestamp.strftime('%Y%m%d')}.csv"
        file_path = failed_dir / filename

        # Convert to DataFrame and save to CSV
        df = pd.DataFrame(failed_urls)
        # Convert any HttpUrl objects to strings
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].apply(
                    lambda x: (
                        str(x)
                        if hasattr(x, "__class__") and "HttpUrl" in x.__class__.__name__
                        else x
                    )
                )

        df.to_csv(file_path, index=False, encoding="utf-8")

        logger.info(f"Saved {len(failed_urls)} failed URLs to {file_path}")
        return file_path

    def save_failed_news(
        self,
        failed_news: List[Dict[str, Any]],
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Optional[Path]:
        """
        Save failed news articles to CSV file in failed subdirectory.

        Args:
            failed_news: List of failed news dictionaries with url and status_code
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file, or None if no failed news
        """
        import pandas as pd

        if not failed_news:
            return None

        if timestamp is None:
            timestamp = datetime.now()

        # Create directory
        failed_dir = newspaper_dir / "failed"
        failed_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        filename = f"failed_news_{timestamp.strftime('%Y%m%d')}.csv"
        file_path = failed_dir / filename

        # Convert to DataFrame and save to CSV
        df = pd.DataFrame(failed_news)
        # Convert any HttpUrl objects to strings
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].apply(
                    lambda x: (
                        str(x)
                        if hasattr(x, "__class__") and "HttpUrl" in x.__class__.__name__
                        else x
                    )
                )

        df.to_csv(file_path, index=False, encoding="utf-8")

        logger.info(f"Saved {len(failed_news)} failed news articles to {file_path}")
        return file_path
