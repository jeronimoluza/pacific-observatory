"""Process-wide pacing + circuit-breaker primitives for Wayback fetching.

The Internet Archive playback endpoint rate-limits per-IP and, under sustained
concurrency, drops connections at the TCP layer ("[Errno 61] Connection
refused") — a burst-triggered blackhole that kills long backfill runs. These
primitives let a run pace itself below the trigger and ride out a blackhole:

- ``RateLimiter`` caps the *total* request rate across all worker threads to a
  gentle target (a shared min-interval gate on a monotonic clock).
- ``CircuitBreaker`` tracks consecutive throttle failures across workers; once
  they cross a threshold it opens for a cooldown so every worker pauses, then
  resumes (the backfill ledger makes resumption idempotent). Repeated trips
  escalate the cooldown up to a cap.
"""

from __future__ import annotations

import time
from threading import Lock


class RateLimiter:
    """Thread-safe minimum-interval gate shared across worker threads."""

    def __init__(self, min_interval: float):
        self._min_interval = max(0.0, min_interval)
        self._lock = Lock()
        self._next_allowed = 0.0

    @classmethod
    def per_second(cls, requests_per_second: float) -> "RateLimiter":
        if requests_per_second <= 0:
            return cls(0.0)
        return cls(1.0 / requests_per_second)

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                if now >= self._next_allowed:
                    self._next_allowed = now + self._min_interval
                    return
                sleep_for = self._next_allowed - now
            time.sleep(sleep_for)


class CircuitBreaker:
    """Shared breaker that opens after N consecutive throttle failures.

    ``record_failure`` / ``record_success`` are called from any worker thread
    after each request; ``wait_if_open`` blocks a worker while the breaker is
    open. Cooldown starts at ``base_cooldown`` and multiplies by
    ``cooldown_factor`` on each subsequent trip, capped at ``max_cooldown``.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        base_cooldown: float = 300.0,
        max_cooldown: float = 900.0,
        cooldown_factor: float = 2.0,
    ):
        self._threshold = failure_threshold
        self._base = base_cooldown
        self._max = max_cooldown
        self._factor = cooldown_factor
        self._lock = Lock()
        self._consecutive = 0
        self._trip_count = 0
        self._open_until = 0.0

    def record_success(self) -> None:
        with self._lock:
            self._consecutive = 0

    def record_failure(self) -> float | None:
        """Count a throttle failure; return the cooldown if this tripped it."""
        with self._lock:
            self._consecutive += 1
            now = time.monotonic()
            if self._consecutive >= self._threshold and now >= self._open_until:
                self._trip_count += 1
                cooldown = min(
                    self._base * (self._factor ** (self._trip_count - 1)),
                    self._max,
                )
                self._open_until = now + cooldown
                self._consecutive = 0
                return cooldown
            return None

    def wait_if_open(self) -> None:
        while True:
            with self._lock:
                remaining = self._open_until - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(remaining)

    def is_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._open_until
