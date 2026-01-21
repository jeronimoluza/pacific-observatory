"""
Structured logging configuration for the text module.

Features:
- JSON-formatted logs to files (one per day)
- Console output for interactive use
- Correlation IDs for request tracing
- Log levels configurable via environment
- Log rotation with RotatingFileHandler

Usage:
    from text.core import configure_logging, get_logger, LogContext

    # Configure at application startup
    configure_logging()

    # Get a logger for your module
    logger = get_logger(__name__)

    # Use correlation IDs for request tracing
    with LogContext(run_id="abc123", newspaper="fiji_sun"):
        logger.info("Starting scrape")
"""

import logging
import logging.handlers
import json
import os
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# Context variables for correlation tracking
_correlation_context: ContextVar[dict] = ContextVar("correlation_context", default={})


@dataclass
class LogContext:
    """
    Context manager for adding correlation context to logs.

    Usage:
        with LogContext(run_id="abc123", newspaper="fiji_sun"):
            logger.info("Processing articles")  # Includes run_id and newspaper
    """

    run_id: Optional[str] = None
    newspaper: Optional[str] = None
    country: Optional[str] = None
    mode: Optional[str] = None
    extra: dict = field(default_factory=dict)

    _token: Any = field(default=None, repr=False)

    def __enter__(self) -> "LogContext":
        context = {
            k: v
            for k, v in {
                "run_id": self.run_id or str(uuid.uuid4())[:8],
                "newspaper": self.newspaper,
                "country": self.country,
                "mode": self.mode,
                **self.extra,
            }.items()
            if v is not None
        }
        self._token = _correlation_context.set(context)
        return self

    def __exit__(self, *args) -> None:
        if self._token is not None:
            _correlation_context.reset(self._token)


def get_correlation_context() -> dict:
    """Get the current correlation context."""
    return _correlation_context.get()


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON-structured log records.

    Each log line is a single JSON object with:
    - timestamp: ISO format timestamp
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - correlation: Correlation context (run_id, newspaper, etc.)
    - extra: Any additional fields
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation context
        correlation = get_correlation_context()
        if correlation:
            log_data["correlation"] = correlation

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the record
        for key in [
            "url",
            "status_code",
            "articles_count",
            "duration_ms",
            "error_type",
            "retry_count",
            "batch_size",
        ]:
            if hasattr(record, key):
                if "extra" not in log_data:
                    log_data["extra"] = {}
                log_data["extra"][key] = getattr(record, key)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.

    Includes correlation context in a compact format:
    [2024-01-15 10:30:45] INFO [fiji_sun] Starting scrape
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        # Add color if enabled
        if self.use_colors and level in self.COLORS:
            level_str = f"{self.COLORS[level]}{level:8s}{self.RESET}"
        else:
            level_str = f"{level:8s}"

        # Build context string
        context = get_correlation_context()
        context_parts = []
        if context.get("newspaper"):
            context_parts.append(context["newspaper"])
        if context.get("run_id"):
            context_parts.append(context["run_id"][:8])

        context_str = f"[{'/'.join(context_parts)}] " if context_parts else ""

        # Format message
        message = record.getMessage()

        # Add exception if present
        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return f"[{timestamp}] {level_str} {context_str}{message}"


def configure_logging(
    log_level: Optional[str] = None,
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    use_colors: bool = True,
) -> None:
    """
    Configure structured logging for the text module.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
                   Defaults to TEXT_LOG_LEVEL env var or INFO.
        log_dir: Directory for log files.
                 Defaults to TEXT_LOG_DIR env var or logs/text/.
        enable_console: Whether to output logs to console.
        enable_file: Whether to output logs to file.
        use_colors: Whether to use colors in console output.

    Example:
        # Basic usage
        configure_logging()

        # Custom configuration
        configure_logging(
            log_level="DEBUG",
            log_dir=Path("/var/log/pacific-observatory"),
            enable_console=True,
            enable_file=True,
        )
    """
    # Determine log level
    level_name = log_level or os.environ.get("TEXT_LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)

    # Determine log directory
    if log_dir is None:
        log_dir_str = os.environ.get("TEXT_LOG_DIR", "logs/text")
        log_dir = Path(log_dir_str)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger for text module
    root_logger = logging.getLogger("text")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(ConsoleFormatter(use_colors=use_colors))
        root_logger.addHandler(console_handler)

    # File handler with daily rotation
    if enable_file:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{today}.jsonl"

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the given module name.

    This ensures all text module loggers are children of the 'text' logger,
    inheriting its configuration.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Processing started", extra={"url": url})
    """
    # Ensure logger is under the text namespace
    if not name.startswith("text"):
        name = f"text.{name}"
    return logging.getLogger(name)


class LoggingMixin:
    """
    Mixin class that provides a logger attribute to classes.

    Usage:
        class MyScraper(LoggingMixin):
            def scrape(self):
                self.logger.info("Scraping...")
    """

    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__module__)
        return self._logger
