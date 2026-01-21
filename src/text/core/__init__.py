"""
Core utilities for the text module.

This module provides:
- Structured logging configuration
- Run tracking database
- Event emission system
- Error handling hierarchy
- Circuit breaker pattern
- Checkpoint/resume system
"""

from .logging_config import configure_logging, get_logger, LogContext
from .events import EventEmitter, ScrapeEvent
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
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    get_circuit_breaker_registry,
)
from .checkpoints import (
    ScrapeCheckpoint,
    CheckpointManager,
    get_checkpoint_manager,
)

__all__ = [
    # Logging
    "configure_logging",
    "get_logger",
    "LogContext",
    # Events
    "EventEmitter",
    "ScrapeEvent",
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
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker",
    "get_circuit_breaker_registry",
    # Checkpoints
    "ScrapeCheckpoint",
    "CheckpointManager",
    "get_checkpoint_manager",
]
