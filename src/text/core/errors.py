"""
Standardized error hierarchy for the text module.

This provides a consistent set of exceptions that can be caught and handled
appropriately throughout the scraping and analysis pipelines.

Exception Hierarchy:
    TextModuleError (base)
    ├── ScraperError
    │   ├── NetworkError
    │   │   └── RateLimitError
    │   └── ParseError
    ├── ConfigError
    ├── StorageError
    └── AnalysisError

Usage:
    from text.core.errors import NetworkError, RateLimitError

    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        raise NetworkError(f"Timeout fetching {url}")
"""

from typing import Optional


class TextModuleError(Exception):
    """Base exception for all text module errors."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class ScraperError(TextModuleError):
    """Base exception for scraper-related errors."""

    def __init__(
        self,
        message: str,
        newspaper: Optional[str] = None,
        url: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        ctx = context or {}
        if newspaper:
            ctx["newspaper"] = newspaper
        if url:
            ctx["url"] = url
        super().__init__(message, ctx)
        self.newspaper = newspaper
        self.url = url


class NetworkError(ScraperError):
    """
    Network-related errors (timeouts, connection failures, HTTP errors).

    Attributes:
        status_code: HTTP status code if applicable
        retry_count: Number of retries attempted
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_count: int = 0,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.retry_count = retry_count
        if status_code:
            self.context["status_code"] = status_code
        if retry_count:
            self.context["retry_count"] = retry_count


class RateLimitError(NetworkError):
    """
    Rate limiting (HTTP 429) errors.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header)
    """

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        kwargs.setdefault("status_code", 429)
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.context["retry_after"] = retry_after


class ParseError(ScraperError):
    """
    HTML/JSON parsing errors.

    Attributes:
        selector: CSS/XPath selector that failed to match
        content_preview: First 200 chars of content that failed to parse
    """

    def __init__(
        self,
        message: str,
        selector: Optional[str] = None,
        content_preview: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.selector = selector
        self.content_preview = content_preview
        if selector:
            self.context["selector"] = selector


class ConfigError(TextModuleError):
    """
    Configuration validation errors.

    Raised when YAML configs are invalid or missing required fields.
    """

    def __init__(
        self,
        message: str,
        config_path: Optional[str] = None,
        field: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        ctx = context or {}
        if config_path:
            ctx["config_path"] = config_path
        if field:
            ctx["field"] = field
        super().__init__(message, ctx)
        self.config_path = config_path
        self.field = field


class StorageError(TextModuleError):
    """
    Storage-related errors (file I/O, CSV parsing, etc.).

    Attributes:
        file_path: Path to the file that caused the error
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, ctx)
        self.file_path = file_path


class AnalysisError(TextModuleError):
    """
    Analysis-related errors (EPU calculation, modeling, etc.).

    Attributes:
        newspaper: Newspaper being analyzed
        country: Country being analyzed
    """

    def __init__(
        self,
        message: str,
        newspaper: Optional[str] = None,
        country: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        ctx = context or {}
        if newspaper:
            ctx["newspaper"] = newspaper
        if country:
            ctx["country"] = country
        super().__init__(message, ctx)
        self.newspaper = newspaper
        self.country = country


class CircuitOpenError(ScraperError):
    """
    Raised when a circuit breaker is open and requests are being rejected.

    Attributes:
        recovery_time: When the circuit breaker will attempt recovery
    """

    def __init__(
        self,
        message: str,
        recovery_time: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.recovery_time = recovery_time
        if recovery_time:
            self.context["recovery_time"] = recovery_time


class CheckpointError(TextModuleError):
    """Errors related to checkpoint save/load operations."""

    def __init__(
        self,
        message: str,
        run_id: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        ctx = context or {}
        if run_id:
            ctx["run_id"] = run_id
        super().__init__(message, ctx)
        self.run_id = run_id
