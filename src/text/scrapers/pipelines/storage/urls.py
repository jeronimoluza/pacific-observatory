"""
URL tracking operations for scraped data.

Manages urls.csv and failed URLs tracking.
"""

import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from ...models import ThumbnailRecord

logger = logging.getLogger(__name__)

FAILED_LEDGER_FILENAME = "failed_urls_seen.csv"
LEDGER_COLUMNS = [
    "url",
    "first_failed_at",
    "last_failed_at",
    "attempts",
    "last_status",
    "last_error",
]
_SEED_DATE_RE = re.compile(r"_(\d{8})\.csv$")

# Chunk size for streaming urls.csv during resume loads. Bounds the resident
# DataFrame to one chunk instead of the whole file.
URLS_LOAD_CHUNKSIZE = 50_000


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
        self, newspaper_dir: Path, skip_urls: Optional[set] = None
    ) -> Optional[List[ThumbnailRecord]]:
        """
        Load thumbnail URLs from urls.csv file.

        Args:
            newspaper_dir: Directory for the newspaper
            skip_urls: Optional set of URL strings to drop. When provided, the
                file is streamed in chunks and each row's ThumbnailRecord is
                constructed transiently and only RETAINED when its url is not in
                this set. This bounds peak retained memory to the number of
                *pending* rows rather than the full file size — a resume run on a
                mostly-drained source no longer holds a pydantic object per
                already-scraped URL for the entire run.

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

        skip = skip_urls or set()
        thumbnails: List[ThumbnailRecord] = []
        try:
            # Stream the file so the resident DataFrame never exceeds one chunk.
            for chunk in pd.read_csv(
                file_path, encoding="utf-8", chunksize=URLS_LOAD_CHUNKSIZE
            ):
                for _, row in chunk.iterrows():
                    try:
                        # Handle NaN values
                        thumb_data = {
                            k: v if pd.notna(v) else None
                            for k, v in row.to_dict().items()
                        }
                        # Build first, then test str(url) so the skip match uses
                        # the same normalized key the scraper compares against.
                        # Skipped records go out of scope here and are freed.
                        thumbnail = ThumbnailRecord(**thumb_data)
                    except Exception as row_error:
                        logger.warning(
                            f"Failed to parse thumbnail row in {file_path}: {row_error}"
                        )
                        continue

                    if skip and str(thumbnail.url) in skip:
                        continue
                    thumbnails.append(thumbnail)

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

    def _ledger_path(self, newspaper_dir: Path) -> Path:
        return newspaper_dir / FAILED_LEDGER_FILENAME

    def _read_ledger(self, newspaper_dir: Path) -> "Optional[Any]":
        import pandas as pd

        ledger_path = self._ledger_path(newspaper_dir)
        if not ledger_path.exists():
            return None
        try:
            df = pd.read_csv(ledger_path, encoding="utf-8", dtype=str)
        except Exception as exc:
            logger.error(f"Failed to read ledger {ledger_path}: {exc}")
            return None
        for col in LEDGER_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[LEDGER_COLUMNS]

    def _write_ledger_atomic(self, newspaper_dir: Path, df) -> Path:
        import pandas as pd  # noqa: F401

        ledger_path = self._ledger_path(newspaper_dir)
        newspaper_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".failed_urls_seen.", suffix=".csv.tmp", dir=str(newspaper_dir)
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            df.to_csv(tmp_path, index=False, encoding="utf-8", columns=LEDGER_COLUMNS)
            os.replace(tmp_path, ledger_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
        return ledger_path

    def _seed_ledger_from_failed_dir(self, newspaper_dir: Path) -> Optional[Path]:
        """
        Build a fresh ``failed_urls_seen.csv`` from any pre-existing
        ``failed/failed_news_*.csv`` and ``failed/failed_urls_*.csv`` snapshots.

        Used once per source on the first run after the ledger feature ships.
        Returns the ledger path on success, or None when there are no source
        files to seed from. Existing snapshot files are not modified.
        """
        import pandas as pd

        failed_dir = newspaper_dir / "failed"
        if not failed_dir.exists() or not failed_dir.is_dir():
            return None

        snapshot_files = sorted(failed_dir.glob("failed_news_*.csv")) + sorted(
            failed_dir.glob("failed_urls_*.csv")
        )
        if not snapshot_files:
            return None

        per_url_first: Dict[str, datetime] = {}
        per_url_last: Dict[str, datetime] = {}

        for snap in snapshot_files:
            ts = self._timestamp_from_snapshot(snap)
            try:
                snap_df = pd.read_csv(snap, encoding="utf-8", dtype=str)
            except Exception as exc:
                logger.warning(f"Failed to read snapshot {snap}: {exc}")
                continue
            if "url" not in snap_df.columns:
                continue
            for url in snap_df["url"].dropna().astype(str).unique():
                if not url:
                    continue
                if url not in per_url_first or ts < per_url_first[url]:
                    per_url_first[url] = ts
                if url not in per_url_last or ts > per_url_last[url]:
                    per_url_last[url] = ts

        if not per_url_first:
            return None

        rows = [
            {
                "url": url,
                "first_failed_at": per_url_first[url].isoformat(),
                "last_failed_at": per_url_last[url].isoformat(),
                "attempts": "1",
                "last_status": "SEED",
                "last_error": "seeded from failed/*.csv",
            }
            for url in per_url_first
        ]
        df = pd.DataFrame(rows, columns=LEDGER_COLUMNS)
        ledger_path = self._write_ledger_atomic(newspaper_dir, df)
        logger.info(
            f"Seeded {len(rows)} URLs into {ledger_path} from {len(snapshot_files)} snapshot file(s)"
        )
        return ledger_path

    @staticmethod
    def _timestamp_from_snapshot(path: Path) -> datetime:
        match = _SEED_DATE_RE.search(path.name)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return datetime.now(tz=timezone.utc)

    def get_failed_url_set(self, newspaper_dir: Path) -> set:
        """
        Return the set of URLs currently recorded in ``failed_urls_seen.csv``.

        If the ledger does not yet exist for this source but historical
        ``failed/failed_*_*.csv`` snapshots are present, auto-seed the ledger
        once and return its URL set. If neither exists, return an empty set.
        """
        df = self._read_ledger(newspaper_dir)
        if df is None:
            seeded = self._seed_ledger_from_failed_dir(newspaper_dir)
            if seeded is None:
                return set()
            df = self._read_ledger(newspaper_dir)
            if df is None:
                return set()
        return set(df["url"].dropna().astype(str).tolist())

    def upsert_failed_urls(
        self, newspaper_dir: Path, entries: List[Dict[str, Any]]
    ) -> Optional[Path]:
        """
        Insert or refresh rows in ``failed_urls_seen.csv`` for the given URLs.

        ``entries`` items are dicts with at least ``url``; ``last_status`` and
        ``last_error`` are optional and default to empty strings. New rows get
        ``attempts=1`` and identical ``first_failed_at`` / ``last_failed_at``.
        Existing rows have ``attempts`` incremented and ``last_failed_at`` /
        ``last_status`` / ``last_error`` refreshed; ``first_failed_at`` is
        preserved.
        """
        import pandas as pd

        if not entries:
            return None

        # Coalesce duplicate URLs in the incoming batch — keep the last entry's
        # status/error but count each occurrence as a single failure for the run.
        coalesced: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            url = entry.get("url")
            if not url:
                continue
            url_str = str(url)
            coalesced[url_str] = {
                "url": url_str,
                "last_status": str(entry.get("last_status") or ""),
                "last_error": str(entry.get("last_error") or "")[:200],
            }
        if not coalesced:
            return None

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        existing = self._read_ledger(newspaper_dir)
        if existing is None or existing.empty:
            rows = [
                {
                    "url": url,
                    "first_failed_at": now_iso,
                    "last_failed_at": now_iso,
                    "attempts": "1",
                    "last_status": payload["last_status"],
                    "last_error": payload["last_error"],
                }
                for url, payload in coalesced.items()
            ]
            df = pd.DataFrame(rows, columns=LEDGER_COLUMNS)
            return self._write_ledger_atomic(newspaper_dir, df)

        existing = existing.copy()
        existing["url"] = existing["url"].astype(str)
        existing_index = {url: idx for idx, url in enumerate(existing["url"].tolist())}
        new_rows = []
        for url, payload in coalesced.items():
            if url in existing_index:
                idx = existing_index[url]
                try:
                    attempts = int(existing.at[idx, "attempts"]) + 1
                except (ValueError, TypeError):
                    attempts = 2
                existing.at[idx, "attempts"] = str(attempts)
                existing.at[idx, "last_failed_at"] = now_iso
                existing.at[idx, "last_status"] = payload["last_status"]
                existing.at[idx, "last_error"] = payload["last_error"]
            else:
                new_rows.append(
                    {
                        "url": url,
                        "first_failed_at": now_iso,
                        "last_failed_at": now_iso,
                        "attempts": "1",
                        "last_status": payload["last_status"],
                        "last_error": payload["last_error"],
                    }
                )
        if new_rows:
            existing = pd.concat(
                [existing, pd.DataFrame(new_rows, columns=LEDGER_COLUMNS)],
                ignore_index=True,
            )
        return self._write_ledger_atomic(newspaper_dir, existing[LEDGER_COLUMNS])

    def evict_from_ledger(self, newspaper_dir: Path, urls: set) -> int:
        """
        Remove rows whose ``url`` is in ``urls`` from ``failed_urls_seen.csv``.

        Returns the number of rows removed. No-op when the ledger is missing.
        """
        if not urls:
            return 0
        df = self._read_ledger(newspaper_dir)
        if df is None or df.empty:
            return 0
        url_set = {str(u) for u in urls}
        before = len(df)
        kept = df[~df["url"].astype(str).isin(url_set)]
        removed = before - len(kept)
        if removed == 0:
            return 0
        if kept.empty:
            ledger_path = self._ledger_path(newspaper_dir)
            empty = (
                kept[LEDGER_COLUMNS]
                if set(LEDGER_COLUMNS).issubset(kept.columns)
                else kept
            )
            self._write_ledger_atomic(newspaper_dir, empty)
            logger.info(f"Evicted {removed} URL(s) from {ledger_path} (now empty)")
            return removed
        self._write_ledger_atomic(newspaper_dir, kept[LEDGER_COLUMNS])
        return removed
