"""
Core utilities for the text module.

This module provides:
- Structured logging configuration
- Run tracking database
- Error handling hierarchy
"""

from .logging_config import configure_logging, get_logger, LogContext
from .run_tracker import RunTracker, ScraperRun
from .errors import (
    TextModuleError,
    ScraperError,
    NetworkError,
    RateLimitError,
    ParseError,
    ConfigError,
    StorageError,
    AnalysisError,
    CircuitOpenError,
    CheckpointError,
)

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    "LogContext",
    # Run tracking
    "RunTracker",
    "ScraperRun",
    # Errors
    "TextModuleError",
    "ScraperError",
    "NetworkError",
    "RateLimitError",
    "ParseError",
    "ConfigError",
    "StorageError",
    "AnalysisError",
    "CircuitOpenError",
    "CheckpointError",
]
