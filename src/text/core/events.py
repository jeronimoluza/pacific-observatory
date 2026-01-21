"""
Event emission system for observability hooks.

This provides a lightweight publish-subscribe pattern for scraper events,
enabling decoupled logging, metrics, and status tracking.

Usage:
    from text.core.events import EventEmitter, ScrapeEvent

    # Create emitter and register handlers
    emitter = EventEmitter()
    emitter.on("scrape_started", lambda e: print(f"Started: {e.newspaper}"))
    emitter.on("article_scraped", lambda e: update_metrics(e))

    # Emit events from scraper
    emitter.emit(ScrapeEvent(
        event_type="scrape_started",
        newspaper="fiji_sun",
        country="fiji",
        run_id="abc123",
    ))
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import logging

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapeEvent:
    """
    Represents a scraper event.

    Event Types:
        - run_started: Scraper run initiated
        - run_completed: Scraper run finished (success or failure)
        - discovery_started: URL discovery phase started
        - discovery_completed: URL discovery phase finished
        - urls_discovered: New URLs found
        - article_started: Starting to scrape an article
        - article_scraped: Article successfully scraped
        - article_failed: Article scraping failed
        - batch_completed: Batch of articles processed
        - rate_limited: Rate limiting detected
        - circuit_opened: Circuit breaker opened
        - circuit_closed: Circuit breaker closed

    Attributes:
        event_type: Type of event (see above)
        newspaper: Newspaper identifier
        country: Country code
        run_id: Correlation ID for the run
        timestamp: When the event occurred
        details: Additional event-specific data
    """

    event_type: str
    newspaper: str
    country: str
    run_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "newspaper": self.newspaper,
            "country": self.country,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


EventHandler = Callable[[ScrapeEvent], None]


class EventEmitter:
    """
    Simple publish-subscribe event emitter.

    Supports registering multiple handlers per event type,
    wildcard handlers for all events, and async-safe operation.

    Example:
        emitter = EventEmitter()

        # Register handler for specific event
        emitter.on("article_scraped", log_article)

        # Register handler for all events
        emitter.on("*", metrics_handler)

        # Emit an event
        emitter.emit(ScrapeEvent(
            event_type="article_scraped",
            newspaper="fiji_sun",
            country="fiji",
            run_id="abc123",
            details={"url": "...", "title": "..."},
        ))
    """

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._enabled = True

    def on(self, event_type: str, handler: EventHandler) -> "EventEmitter":
        """
        Register an event handler.

        Args:
            event_type: Event type to listen for, or "*" for all events
            handler: Callable that receives a ScrapeEvent

        Returns:
            Self for chaining
        """
        self._handlers[event_type].append(handler)
        return self

    def off(
        self, event_type: str, handler: Optional[EventHandler] = None
    ) -> "EventEmitter":
        """
        Unregister an event handler.

        Args:
            event_type: Event type to unregister from
            handler: Specific handler to remove, or None to remove all

        Returns:
            Self for chaining
        """
        if handler is None:
            self._handlers[event_type] = []
        elif handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
        return self

    def emit(self, event: ScrapeEvent) -> None:
        """
        Emit an event to all registered handlers.

        Handlers are called synchronously in registration order.
        Exceptions in handlers are logged but don't stop other handlers.

        Args:
            event: The event to emit
        """
        if not self._enabled:
            return

        # Call specific handlers
        for handler in self._handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.warning(
                    f"Event handler failed for {event.event_type}: {e}",
                    exc_info=True,
                )

        # Call wildcard handlers
        for handler in self._handlers["*"]:
            try:
                handler(event)
            except Exception as e:
                logger.warning(
                    f"Wildcard event handler failed for {event.event_type}: {e}",
                    exc_info=True,
                )

    def disable(self) -> None:
        """Disable event emission (for testing)."""
        self._enabled = False

    def enable(self) -> None:
        """Enable event emission."""
        self._enabled = True

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()


class LoggingHandler:
    """
    Event handler that logs events using structured logging.

    Example:
        emitter.on("*", LoggingHandler())
    """

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level
        self.logger = get_logger("events")

    def __call__(self, event: ScrapeEvent) -> None:
        msg = f"{event.event_type}: {event.newspaper}"
        if event.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in event.details.items())
            msg += f" ({detail_str})"
        self.logger.log(self.log_level, msg)


class ConsoleProgressHandler:
    """
    Event handler that shows progress in the console.

    Provides a simple progress display without requiring rich/tqdm.

    Example:
        emitter.on("*", ConsoleProgressHandler())
    """

    def __init__(self):
        self._articles_scraped = 0
        self._articles_failed = 0
        self._current_newspaper = None

    def __call__(self, event: ScrapeEvent) -> None:
        if event.event_type == "run_started":
            self._current_newspaper = event.newspaper
            self._articles_scraped = 0
            self._articles_failed = 0
            print(f"\n=== Starting: {event.newspaper} ({event.country}) ===")

        elif event.event_type == "urls_discovered":
            count = event.details.get("count", 0)
            print(f"  Discovered {count} URLs")

        elif event.event_type == "article_scraped":
            self._articles_scraped += 1
            if self._articles_scraped % 10 == 0:
                print(f"  Scraped: {self._articles_scraped} articles", end="\r")

        elif event.event_type == "article_failed":
            self._articles_failed += 1

        elif event.event_type == "run_completed":
            status = event.details.get("status", "unknown")
            duration = event.details.get("duration_seconds", 0)
            print(f"\n  Completed: {status.upper()}")
            print(
                f"  Articles: {self._articles_scraped} scraped, {self._articles_failed} failed"
            )
            print(f"  Duration: {duration:.1f}s")


# Global default emitter
_default_emitter: Optional[EventEmitter] = None


def get_emitter() -> EventEmitter:
    """Get the global default event emitter."""
    global _default_emitter
    if _default_emitter is None:
        _default_emitter = EventEmitter()
    return _default_emitter


def set_emitter(emitter: EventEmitter) -> None:
    """Set the global default event emitter."""
    global _default_emitter
    _default_emitter = emitter
