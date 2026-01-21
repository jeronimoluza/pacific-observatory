"""
SQLite-based run tracking for scraper observability.

Tracks scraper runs, success/failure counts, timing, and individual article results.
This is metadata only - article data still goes to CSV files.

Usage:
    from text.core.run_tracker import RunTracker, ScraperRun

    tracker = RunTracker()

    # Start a run
    run = tracker.start_run(
        newspaper="fiji_sun",
        country="fiji",
        mode="update",
    )

    # Update progress
    tracker.update_run(run.run_id, articles_found=50)

    # Complete the run
    tracker.complete_run(run.run_id, status="success", articles_scraped=48)

    # Query history
    recent = tracker.get_recent_runs(hours=24)
    failures = tracker.get_failures(days=7)
"""

import sqlite3
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .logging_config import get_logger
from .events import ScrapeEvent

logger = get_logger(__name__)


@dataclass
class ScraperRun:
    """Represents a single scraper run."""

    run_id: str
    newspaper: str
    country: str
    mode: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    articles_found: int = 0
    articles_scraped: int = 0
    articles_failed: int = 0
    error_message: Optional[str] = None
    config_hash: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ScraperRun":
        """Create a ScraperRun from a database row."""
        return cls(
            run_id=row["run_id"],
            newspaper=row["newspaper"],
            country=row["country"],
            mode=row["mode"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            status=row["status"],
            articles_found=row["articles_found"] or 0,
            articles_scraped=row["articles_scraped"] or 0,
            articles_failed=row["articles_failed"] or 0,
            error_message=row["error_message"],
            config_hash=row["config_hash"],
        )


@dataclass
class ArticleResult:
    """Represents the result of scraping a single article."""

    run_id: str
    url: str
    status: str  # success, failed, skipped
    error_type: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)


class RunTracker:
    """
    SQLite-based tracker for scraper runs.

    Database is stored at data/text/scraper_runs.db by default.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS scraper_runs (
        id INTEGER PRIMARY KEY,
        run_id TEXT UNIQUE NOT NULL,
        newspaper TEXT NOT NULL,
        country TEXT NOT NULL,
        mode TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'running',
        articles_found INTEGER DEFAULT 0,
        articles_scraped INTEGER DEFAULT 0,
        articles_failed INTEGER DEFAULT 0,
        error_message TEXT,
        config_hash TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_runs_newspaper ON scraper_runs(newspaper);
    CREATE INDEX IF NOT EXISTS idx_runs_country ON scraper_runs(country);
    CREATE INDEX IF NOT EXISTS idx_runs_status ON scraper_runs(status);
    CREATE INDEX IF NOT EXISTS idx_runs_started ON scraper_runs(started_at);

    CREATE TABLE IF NOT EXISTS article_results (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        url TEXT NOT NULL,
        status TEXT NOT NULL,
        error_type TEXT,
        scraped_at TIMESTAMP NOT NULL,
        FOREIGN KEY (run_id) REFERENCES scraper_runs(run_id)
    );

    CREATE INDEX IF NOT EXISTS idx_articles_run ON article_results(run_id);
    CREATE INDEX IF NOT EXISTS idx_articles_status ON article_results(status);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the run tracker.

        Args:
            db_path: Path to SQLite database. Defaults to data/text/scraper_runs.db
        """
        if db_path is None:
            db_path = Path("data/text/scraper_runs.db")

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        logger.debug(f"Initialized run tracker at {self.db_path}")

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def start_run(
        self,
        newspaper: str,
        country: str,
        mode: str,
        config_hash: Optional[str] = None,
    ) -> ScraperRun:
        """
        Start tracking a new scraper run.

        Args:
            newspaper: Newspaper identifier
            country: Country code
            mode: Scrape mode (full, update, discover, etc.)
            config_hash: Hash of the config file for versioning

        Returns:
            ScraperRun object with generated run_id
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        run = ScraperRun(
            run_id=run_id,
            newspaper=newspaper,
            country=country,
            mode=mode,
            started_at=started_at,
            config_hash=config_hash,
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scraper_runs
                (run_id, newspaper, country, mode, started_at, status, config_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    newspaper,
                    country,
                    mode,
                    started_at.isoformat(),
                    "running",
                    config_hash,
                ),
            )

        logger.info(f"Started run {run_id[:8]} for {newspaper}")
        return run

    def update_run(
        self,
        run_id: str,
        articles_found: Optional[int] = None,
        articles_scraped: Optional[int] = None,
        articles_failed: Optional[int] = None,
    ) -> None:
        """
        Update progress counters for a run.

        Args:
            run_id: Run identifier
            articles_found: Total articles discovered
            articles_scraped: Articles successfully scraped
            articles_failed: Articles that failed
        """
        updates = []
        params = []

        if articles_found is not None:
            updates.append("articles_found = ?")
            params.append(articles_found)
        if articles_scraped is not None:
            updates.append("articles_scraped = ?")
            params.append(articles_scraped)
        if articles_failed is not None:
            updates.append("articles_failed = ?")
            params.append(articles_failed)

        if not updates:
            return

        params.append(run_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE scraper_runs SET {', '.join(updates)} WHERE run_id = ?",
                params,
            )

    def complete_run(
        self,
        run_id: str,
        status: str,
        articles_scraped: Optional[int] = None,
        articles_failed: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Mark a run as completed.

        Args:
            run_id: Run identifier
            status: Final status (success, failed, partial)
            articles_scraped: Final count of scraped articles
            articles_failed: Final count of failed articles
            error_message: Error message if failed
        """
        completed_at = datetime.utcnow()

        with self._connect() as conn:
            updates = ["completed_at = ?", "status = ?"]
            params = [completed_at.isoformat(), status]

            if articles_scraped is not None:
                updates.append("articles_scraped = ?")
                params.append(articles_scraped)
            if articles_failed is not None:
                updates.append("articles_failed = ?")
                params.append(articles_failed)
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message[:1000])  # Truncate long messages

            params.append(run_id)

            conn.execute(
                f"UPDATE scraper_runs SET {', '.join(updates)} WHERE run_id = ?",
                params,
            )

        logger.info(f"Completed run {run_id[:8]} with status {status}")

    def record_article(
        self,
        run_id: str,
        url: str,
        status: str,
        error_type: Optional[str] = None,
    ) -> None:
        """
        Record the result of scraping a single article.

        Args:
            run_id: Run identifier
            url: Article URL
            status: Result status (success, failed, skipped)
            error_type: Type of error if failed
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO article_results (run_id, url, status, error_type, scraped_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, url, status, error_type, datetime.utcnow().isoformat()),
            )

    def get_run(self, run_id: str) -> Optional[ScraperRun]:
        """Get a specific run by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scraper_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        return ScraperRun.from_row(row) if row else None

    def get_recent_runs(
        self,
        hours: int = 24,
        newspaper: Optional[str] = None,
        country: Optional[str] = None,
    ) -> List[ScraperRun]:
        """
        Get runs from the last N hours.

        Args:
            hours: Number of hours to look back
            newspaper: Filter by newspaper (optional)
            country: Filter by country (optional)

        Returns:
            List of ScraperRun objects, most recent first
        """
        since = datetime.utcnow() - timedelta(hours=hours)

        query = "SELECT * FROM scraper_runs WHERE started_at > ?"
        params: List[Any] = [since.isoformat()]

        if newspaper:
            query += " AND newspaper = ?"
            params.append(newspaper)
        if country:
            query += " AND country = ?"
            params.append(country)

        query += " ORDER BY started_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [ScraperRun.from_row(row) for row in rows]

    def get_failures(
        self,
        days: int = 7,
        newspaper: Optional[str] = None,
    ) -> List[ScraperRun]:
        """
        Get failed runs from the last N days.

        Args:
            days: Number of days to look back
            newspaper: Filter by newspaper (optional)

        Returns:
            List of failed ScraperRun objects
        """
        since = datetime.utcnow() - timedelta(days=days)

        query = "SELECT * FROM scraper_runs WHERE status = 'failed' AND started_at > ?"
        params: List[Any] = [since.isoformat()]

        if newspaper:
            query += " AND newspaper = ?"
            params.append(newspaper)

        query += " ORDER BY started_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [ScraperRun.from_row(row) for row in rows]

    def get_newspaper_stats(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get aggregate statistics per newspaper.

        Args:
            days: Number of days to include

        Returns:
            List of dicts with newspaper stats
        """
        since = datetime.utcnow() - timedelta(days=days)

        query = """
            SELECT
                newspaper,
                country,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failure_count,
                SUM(articles_scraped) as total_articles,
                MAX(started_at) as last_run
            FROM scraper_runs
            WHERE started_at > ?
            GROUP BY newspaper, country
            ORDER BY newspaper
        """

        with self._connect() as conn:
            rows = conn.execute(query, (since.isoformat(),)).fetchall()

        return [dict(row) for row in rows]

    def get_last_successful_run(self, newspaper: str) -> Optional[ScraperRun]:
        """Get the most recent successful run for a newspaper."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM scraper_runs
                WHERE newspaper = ? AND status = 'success'
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (newspaper,),
            ).fetchone()

        return ScraperRun.from_row(row) if row else None

    def cleanup_old_runs(self, days: int = 90) -> int:
        """
        Delete runs older than N days.

        Args:
            days: Delete runs older than this

        Returns:
            Number of runs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self._connect() as conn:
            # Delete article results first (foreign key)
            conn.execute(
                """
                DELETE FROM article_results
                WHERE run_id IN (
                    SELECT run_id FROM scraper_runs WHERE started_at < ?
                )
                """,
                (cutoff.isoformat(),),
            )

            # Delete runs
            cursor = conn.execute(
                "DELETE FROM scraper_runs WHERE started_at < ?",
                (cutoff.isoformat(),),
            )

        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} runs older than {days} days")

        return deleted


class DatabaseEventHandler:
    """
    Event handler that records events to the run tracker database.

    Usage:
        tracker = RunTracker()
        emitter = EventEmitter()
        emitter.on("*", DatabaseEventHandler(tracker))
    """

    def __init__(self, tracker: RunTracker):
        self.tracker = tracker
        self._run_id: Optional[str] = None

    def __call__(self, event: ScrapeEvent) -> None:
        if event.event_type == "run_started":
            run = self.tracker.start_run(
                newspaper=event.newspaper,
                country=event.country,
                mode=event.details.get("mode", "unknown"),
                config_hash=event.details.get("config_hash"),
            )
            self._run_id = run.run_id

        elif event.event_type == "urls_discovered":
            if self._run_id:
                self.tracker.update_run(
                    self._run_id,
                    articles_found=event.details.get("count", 0),
                )

        elif event.event_type == "article_scraped":
            if self._run_id:
                self.tracker.record_article(
                    self._run_id,
                    url=event.details.get("url", ""),
                    status="success",
                )

        elif event.event_type == "article_failed":
            if self._run_id:
                self.tracker.record_article(
                    self._run_id,
                    url=event.details.get("url", ""),
                    status="failed",
                    error_type=event.details.get("error_type"),
                )

        elif event.event_type == "run_completed":
            if self._run_id:
                self.tracker.complete_run(
                    self._run_id,
                    status=event.details.get("status", "unknown"),
                    articles_scraped=event.details.get("articles_scraped"),
                    articles_failed=event.details.get("articles_failed"),
                    error_message=event.details.get("error_message"),
                )


def compute_config_hash(config_path: Path) -> str:
    """Compute a hash of a config file for versioning."""
    content = config_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:12]
