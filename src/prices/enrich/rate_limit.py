"""Proactive per-model rate-limit throttle for tier-c / embedding calls.

Three independent ceilings per model:
    RPM — requests per rolling 60s window
    TPM — tokens per rolling 60s window
    RPD — requests per UTC day (persisted across process restarts)

`acquire(model, estimated_tokens)` is an async coroutine that blocks until
all three buckets have headroom for one more call. The estimate is replaced
with the actual usage via `record_actual(model, actual_tokens)` after the
call returns — this corrects TPM drift when the estimate was off.

`DailyQuotaExhausted` is raised when RPD has no slot today; callers should
let this propagate so the run halts cleanly instead of burning more retries.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

import yaml

from prices.enrich import config


class DailyQuotaExhausted(RuntimeError):
    """Raised when the RPD ceiling has been hit for the current UTC day."""


_WINDOW_SEC = 60.0


class _Bucket:
    """Per-model rolling-window bucket. Not thread-safe — guard with the
    module-level asyncio.Lock when used from concurrent coroutines."""

    def __init__(self, model: str, rpm: int, tpm: int, rpd: int) -> None:
        self.model = model
        self.rpm = max(1, int(rpm * config.RATE_LIMIT_HEADROOM_RATIO))
        self.tpm = max(1_000, int(tpm * config.RATE_LIMIT_HEADROOM_RATIO))
        self.rpd = max(1, rpd)
        self.req_times: deque[float] = deque()
        self.tok_times: deque[tuple[float, int]] = deque()
        self.day: str = ""
        self.day_requests: int = 0

    def _prune(self, now: float) -> None:
        cutoff = now - _WINDOW_SEC
        while self.req_times and self.req_times[0] < cutoff:
            self.req_times.popleft()
        while self.tok_times and self.tok_times[0][0] < cutoff:
            self.tok_times.popleft()

    def _roll_day(self, today: str) -> None:
        if self.day != today:
            self.day = today
            self.day_requests = 0

    def can_acquire(
        self, estimated_tokens: int, today: str, now: float
    ) -> Optional[float]:
        """Return None if acquire is OK now, else seconds to wait. Raises
        DailyQuotaExhausted if RPD is exhausted for the current UTC day."""
        self._roll_day(today)
        if self.day_requests >= self.rpd:
            raise DailyQuotaExhausted(
                f"{self.model}: RPD {self.day_requests}/{self.rpd} exhausted for {today}"
            )
        self._prune(now)
        waits = []
        if len(self.req_times) >= self.rpm:
            waits.append(_WINDOW_SEC - (now - self.req_times[0]) + 0.05)
        tok_used = sum(t for _, t in self.tok_times)
        if tok_used + estimated_tokens > self.tpm:
            if self.tok_times:
                waits.append(_WINDOW_SEC - (now - self.tok_times[0][0]) + 0.05)
            else:
                waits.append(0.1)
        return max(waits) if waits else None

    def record(self, tokens: int, today: str, now: float) -> None:
        self._roll_day(today)
        self.req_times.append(now)
        self.tok_times.append((now, max(0, int(tokens))))
        self.day_requests += 1

    def record_actual(self, tokens: int) -> None:
        """Replace the last token reading with the actual count returned by
        the model. Keeps TPM accurate when the upfront estimate was wrong."""
        if not self.tok_times:
            return
        ts, _ = self.tok_times[-1]
        self.tok_times[-1] = (ts, max(0, int(tokens)))


def _load_overrides() -> dict[str, dict[str, int]]:
    p = config.RATE_LIMITS_OVERRIDE_PATH
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out: dict[str, dict[str, int]] = {}
    for model, lim in data.items():
        if isinstance(lim, dict):
            out[str(model)] = {
                "rpm": int(lim.get("rpm", 0)) or 1,
                "tpm": int(lim.get("tpm", 0)) or 1_000,
                "rpd": int(lim.get("rpd", 0)) or 1,
            }
    return out


def _build_bucket(model: str) -> _Bucket:
    overrides = _load_overrides()
    lim = overrides.get(model) or config.RATE_LIMITS.get(model)
    if lim is None:
        lim = {"rpm": 60, "tpm": 60_000, "rpd": 10_000}
    return _Bucket(model, lim["rpm"], lim["tpm"], lim["rpd"])


_BUCKETS: dict[str, _Bucket] = {}
_LOCK = asyncio.Lock()


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _state_load() -> dict:
    p = config.RATE_LIMITS_STATE_PATH
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _state_save(state: dict) -> None:
    p = config.RATE_LIMITS_STATE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


def _hydrate_rpd(model: str, bucket: _Bucket, today: str) -> None:
    state = _state_load()
    cell = state.get(model, {})
    if cell.get("day") == today:
        bucket.day = today
        bucket.day_requests = int(cell.get("requests", 0))


def _persist_rpd(model: str, bucket: _Bucket) -> None:
    state = _state_load()
    state[model] = {"day": bucket.day, "requests": bucket.day_requests}
    _state_save(state)


async def acquire(model: str, estimated_tokens: Optional[int] = None) -> None:
    """Block until the (model) bucket has headroom for one more call.
    Raises DailyQuotaExhausted if RPD is spent for the current UTC day."""
    if estimated_tokens is None:
        estimated_tokens = config.RATE_LIMIT_TOKEN_ESTIMATE_PER_CALL
    while True:
        async with _LOCK:
            if model not in _BUCKETS:
                _BUCKETS[model] = _build_bucket(model)
                _hydrate_rpd(model, _BUCKETS[model], _utc_today())
            bucket = _BUCKETS[model]
            today = _utc_today()
            now = time.time()
            wait = bucket.can_acquire(estimated_tokens, today, now)
            if wait is None:
                bucket.record(estimated_tokens, today, now)
                _persist_rpd(model, bucket)
                return
        await asyncio.sleep(min(wait, _WINDOW_SEC))


def record_actual(model: str, actual_tokens: int) -> None:
    """Replace the last per-call token estimate with the real usage."""
    bucket = _BUCKETS.get(model)
    if bucket is not None:
        bucket.record_actual(actual_tokens)


def snapshot() -> dict[str, dict]:
    """Diagnostics — current bucket state for STATUS.md / telemetry."""
    out: dict[str, dict] = {}
    now = time.time()
    today = _utc_today()
    for model, bucket in _BUCKETS.items():
        bucket._prune(now)
        bucket._roll_day(today)
        tok_used = sum(t for _, t in bucket.tok_times)
        out[model] = {
            "rpm_used": len(bucket.req_times),
            "rpm_limit": bucket.rpm,
            "tpm_used": tok_used,
            "tpm_limit": bucket.tpm,
            "rpd_used": bucket.day_requests,
            "rpd_limit": bucket.rpd,
        }
    return out
