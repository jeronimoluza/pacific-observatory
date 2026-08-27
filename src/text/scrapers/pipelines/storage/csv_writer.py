"""
CSV file operations for article storage.

Handles writing articles to CSV files in both batch and streaming modes.
"""

import csv
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ...models import ArticleRecord

logger = logging.getLogger(__name__)

# Canonical column order for all CSV files - single source of truth
CSV_COLUMNS = [
    "url",
    "title",
    "date",
    "body",
    "tags",
    "source",
    "country",
    "language",
    "_scraped_at",
]


class CSVWriter:
    """Handles CSV file operations for article storage."""

    def __init__(self, base_data_dir: Path):
        """
        Initialize CSV writer.

        Args:
            base_data_dir: Base directory for data storage
        """
        self.base_data_dir = base_data_dir

    def initialize_csv(
        self,
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Path:
        """
        Initialize CSV file with headers for streaming writes.

        Args:
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the initialized CSV file
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create directory
        newspaper_dir.mkdir(parents=True, exist_ok=True)

        # Create filename
        filename = "news.csv"
        file_path = newspaper_dir / filename

        # Write headers to file with explicit flush
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                f.flush()  # Ensure headers are written to disk

            # Verify headers were written
            with open(file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                expected_header = ",".join(CSV_COLUMNS)
                if first_line != expected_header:
                    logger.error(
                        f"Header mismatch! Expected: {expected_header}, Got: {first_line}"
                    )
                    raise ValueError(
                        f"CSV headers not written correctly to {file_path}"
                    )

            logger.info(f"Initialized CSV file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to initialize CSV file {file_path}: {e}")
            raise

        return file_path

    def append_article(
        self,
        article: ArticleRecord,
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Path:
        """
        Append a single article to the CSV file (streaming write).

        Args:
            article: ArticleRecord object to append
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for metadata

        Returns:
            Path to the CSV file
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create directory if needed
        newspaper_dir.mkdir(parents=True, exist_ok=True)

        # Get file path
        filename = "news.csv"
        file_path = newspaper_dir / filename

        # Ensure file exists with correct headers
        file_exists = file_path.exists()
        if file_exists:
            # Check existing headers and migrate if needed
            existing_headers = self._read_csv_header(file_path)
            if existing_headers != CSV_COLUMNS:
                self._migrate_csv_headers(file_path, existing_headers, CSV_COLUMNS)
        else:
            # File doesn't exist, create it with headers
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                f.flush()
            logger.info(f"Created CSV file with headers: {file_path}")

        # Convert article to dictionary
        article_dict = article.model_dump()

        # Convert tags list to comma-separated string
        if isinstance(article_dict.get("tags"), list):
            article_dict["tags"] = ",".join(article_dict["tags"])

        # Convert HttpUrl to string
        article_dict["url"] = str(article_dict["url"])

        # Add timestamp
        article_dict["_scraped_at"] = timestamp.isoformat()

        # Build row with only the fields in CSV_COLUMNS, in the correct order
        row = {}
        for col in CSV_COLUMNS:
            row[col] = article_dict.get(col, "")

        # Append to CSV file
        with open(file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=CSV_COLUMNS, restval="", extrasaction="ignore"
            )
            writer.writerow(row)

        return file_path

    def save_articles(
        self,
        articles: List[ArticleRecord],
        newspaper_dir: Path,
        timestamp: datetime = None,
    ) -> Path:
        """
        Save article records to CSV file (batch mode).

        Args:
            articles: List of ArticleRecord objects
            newspaper_dir: Directory for the newspaper
            timestamp: Optional timestamp for filename

        Returns:
            Path to the saved file
        """
        import pandas as pd

        if timestamp is None:
            timestamp = datetime.now()

        # Create directory
        newspaper_dir.mkdir(parents=True, exist_ok=True)

        # Create filename - articles are saved as news.csv
        filename = "news.csv"
        file_path = newspaper_dir / filename

        # Convert articles to dictionaries
        data = []
        for article in articles:
            article_dict = article.model_dump()
            article_dict["_scraped_at"] = timestamp.isoformat()
            # Convert tags list to comma-separated string
            if isinstance(article_dict.get("tags"), list):
                article_dict["tags"] = ",".join(article_dict["tags"])
            # Convert HttpUrl to string
            article_dict["url"] = str(article_dict["url"])
            data.append(article_dict)

        # Create DataFrame and save to CSV with explicit column order
        df = pd.DataFrame(data)
        # Ensure all columns exist and are in canonical order
        for col in CSV_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[CSV_COLUMNS]
        df.to_csv(file_path, index=None, encoding="utf-8")

        logger.info(f"Saved {len(articles)} articles to {file_path}")
        return file_path

    def load_existing_articles(
        self, newspaper_dir: Path
    ) -> Optional[List[ArticleRecord]]:
        """
        Load existing articles from news.csv file.

        Args:
            newspaper_dir: Directory for the newspaper

        Returns:
            List of ArticleRecord objects if file exists, None otherwise
        """
        import pandas as pd

        # Check for news.csv file
        filename = "news.csv"
        file_path = newspaper_dir / filename

        if not file_path.exists():
            logger.info(f"No existing articles file found: {file_path}")
            return None

        try:
            # Read CSV file
            df = pd.read_csv(file_path, encoding="utf-8")
            articles = []

            for _, row in df.iterrows():
                try:
                    # Convert row to dictionary
                    article_data = row.to_dict()

                    # Remove metadata fields that aren't part of ArticleRecord
                    article_data = {
                        k: v for k, v in article_data.items() if not k.startswith("_")
                    }

                    # Handle NaN values
                    article_data = {
                        k: v if pd.notna(v) else None for k, v in article_data.items()
                    }

                    # Parse tags from comma-separated string back to list
                    if "tags" in article_data and isinstance(article_data["tags"], str):
                        article_data["tags"] = [
                            tag.strip()
                            for tag in article_data["tags"].split(",")
                            if tag.strip()
                        ]

                    article = ArticleRecord(**article_data)
                    articles.append(article)
                except Exception as row_error:
                    logger.warning(
                        f"Failed to parse article row in {file_path}: {row_error}"
                    )
                    continue

            logger.info(f"Loaded {len(articles)} existing articles from {file_path}")
            return articles

        except Exception as e:
            logger.error(f"Failed to load existing articles from {file_path}: {e}")
            return None

    def get_existing_article_urls(self, newspaper_dir: Path) -> set:
        """
        Get set of existing article URLs from news.csv file.

        Args:
            newspaper_dir: Directory for the newspaper

        Returns:
            Set of existing article URLs
        """
        import pandas as pd

        # Check for news.csv file
        filename = "news.csv"
        file_path = newspaper_dir / filename

        if not file_path.exists():
            logger.info(f"No existing articles file found: {file_path}")
            return set()

        try:
            # Read only the url column — article bodies are the bulk of this
            # file and materializing them here costs GBs of RSS per source.
            df = pd.read_csv(file_path, encoding="utf-8", usecols=["url"], dtype=str)
            urls = set(df["url"].astype(str).unique())
            logger.info(f"Found {len(urls)} existing article URLs")
            return urls

        except Exception as e:
            logger.error(f"Failed to get existing article URLs from {file_path}: {e}")
            return set()

    def _read_csv_header(self, file_path: Path) -> List[str]:
        """
        Read the header row of an existing CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            List of column names from the header row
        """
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            return next(reader)

    def _migrate_csv_headers(
        self, file_path: Path, old_headers: List[str], new_headers: List[str]
    ) -> None:
        """
        Migrate CSV to have new header columns.

        Adds missing columns with empty values. This handles the case where
        an existing CSV has fewer columns than the current schema.

        Args:
            file_path: Path to the CSV file
            old_headers: Current headers in the file
            new_headers: Target headers (canonical column order)
        """
        logger.info(
            f"Migrating CSV headers in {file_path}: {old_headers} -> {new_headers}"
        )

        # Create a mapping from old column positions to new positions
        old_to_new_index = {}
        for i, old_col in enumerate(old_headers):
            if old_col in new_headers:
                old_to_new_index[i] = new_headers.index(old_col)

        # Read all rows and rewrite with new headers
        rows = []
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader)  # Skip old header
            for row in reader:
                # Create new row with empty values for missing columns
                new_row = [""] * len(new_headers)
                for old_idx, new_idx in old_to_new_index.items():
                    if old_idx < len(row):
                        new_row[new_idx] = row[old_idx]
                rows.append(new_row)

        # Write to temp file first, then atomically replace
        temp_fd, temp_path = tempfile.mkstemp(suffix=".csv")
        try:
            with open(temp_fd, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(new_headers)
                writer.writerows(rows)

            # Atomically replace original file
            shutil.move(temp_path, file_path)
            logger.info(f"Successfully migrated {len(rows)} rows in {file_path}")
        except Exception as e:
            # Clean up temp file on error
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise e
