"""
Circuit breaker pattern implementation for resilient scraping.

Prevents repeated requests to failing newspapers by tracking failures
and temporarily blocking requests when a threshold is exceeded.

States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, all requests rejected immediately
    - HALF_OPEN: Testing if target recovered

Usage:
    from text.core.circuit_breaker import CircuitBreaker, CircuitOpenError

    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=timedelta(minutes=30))

    async def fetch_with_circuit_breaker(url: str):
        async def fetch():
            return await http_client.get(url)

        return await breaker.call(fetch)

    # Or use as decorator
    @breaker
    async def fetch_article(url: str):
        return await http_client.get(url)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, Optional, TypeVar
import functools

from .logging_config import get_logger
from .errors import CircuitOpenError

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for resilient external calls.

    When failures exceed the threshold, the circuit opens and rejects
    all calls immediately. After the recovery timeout, it transitions
    to half-open state and allows a test request through.

    Attributes:
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Time to wait before attempting recovery
        half_open_requests: Number of test requests in half-open state
        name: Optional name for logging
    """

    failure_threshold: int = 5
    recovery_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    half_open_requests: int = 1
    name: str = "default"

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _half_open_successes: int = field(default=0, init=False)
    _stats: CircuitStats = field(default_factory=CircuitStats, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if the circuit is open (blocking requests)."""
        return self._state == CircuitState.OPEN

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = datetime.utcnow() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._stats.state_changes += 1
            logger.info(
                f"Circuit '{self.name}' transitioned from {old_state.value} to {new_state.value}"
            )

    def _on_success(self) -> None:
        """Handle a successful call."""
        self._stats.successful_calls += 1
        self._stats.last_success_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_requests:
                # Recovery successful, close the circuit
                self._transition_to(CircuitState.CLOSED)
                self._failure_count = 0
                self._half_open_successes = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        """Handle a failed call."""
        self._stats.failed_calls += 1
        self._stats.last_failure_time = datetime.utcnow()
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            # Recovery failed, reopen the circuit
            self._transition_to(CircuitState.OPEN)
            self._half_open_successes = 0
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                # Too many failures, open the circuit
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"Circuit '{self.name}' opened after {self._failure_count} failures"
                )

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            CircuitOpenError: If the circuit is open and not ready for recovery
        """
        async with self._lock:
            self._stats.total_calls += 1

            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self._stats.rejected_calls += 1
                    recovery_time = self._last_failure_time + self.recovery_timeout
                    raise CircuitOpenError(
                        f"Circuit '{self.name}' is open",
                        recovery_time=recovery_time.isoformat(),
                    )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Use the circuit breaker as a decorator.

        Example:
            breaker = CircuitBreaker()

            @breaker
            async def fetch_data():
                return await http_client.get(url)
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_successes = 0
        logger.info(f"Circuit '{self.name}' reset to closed state")


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides a centralized way to manage circuit breakers per newspaper
    or other resource.

    Usage:
        registry = CircuitBreakerRegistry()
        breaker = registry.get("fiji_sun")

        async def scrape():
            return await breaker.call(fetch_article)
    """

    def __init__(
        self,
        default_failure_threshold: int = 5,
        default_recovery_timeout: timedelta = timedelta(minutes=30),
    ):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_failure_threshold = default_failure_threshold
        self._default_recovery_timeout = default_recovery_timeout

    def get(self, name: str) -> CircuitBreaker:
        """
        Get or create a circuit breaker for the given name.

        Args:
            name: Name of the circuit breaker (e.g., newspaper name)

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=self._default_failure_threshold,
                recovery_timeout=self._default_recovery_timeout,
            )
        return self._breakers[name]

    def reset(self, name: str) -> None:
        """Reset a specific circuit breaker."""
        if name in self._breakers:
            self._breakers[name].reset()

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_stats(self) -> Dict[str, CircuitStats]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.stats for name, breaker in self._breakers.items()}

    def get_open_circuits(self) -> list:
        """Get names of all open circuits."""
        return [name for name, breaker in self._breakers.items() if breaker.is_open]


# Global registry instance
_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get a circuit breaker from the global registry."""
    return get_circuit_breaker_registry().get(name)
