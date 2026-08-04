"""Unit tests for Wayback fetch hardening: pacing, Retry-After, breaker, reuse."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from prices import backfill
from prices._shared import wayback
from prices._shared.pacing import CircuitBreaker, RateLimiter


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rate_limiter_enforces_min_interval():
    limiter = RateLimiter(min_interval=0.05)
    start = time.monotonic()
    for _ in range(4):  # 4 grants → at least 3 intervals of spacing
        limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15 - 0.01


@pytest.mark.unit
def test_rate_limiter_zero_interval_never_sleeps():
    limiter = RateLimiter.per_second(0)  # disabled
    start = time.monotonic()
    for _ in range(50):
        limiter.wait()
    assert time.monotonic() - start < 0.05


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_breaker_trips_after_threshold_and_releases_after_cooldown():
    breaker = CircuitBreaker(failure_threshold=3, base_cooldown=0.1, max_cooldown=0.1)
    assert breaker.record_failure() is None
    assert breaker.record_failure() is None
    cooldown = breaker.record_failure()  # 3rd consecutive → trips
    assert cooldown == pytest.approx(0.1)
    assert breaker.is_open()

    start = time.monotonic()
    breaker.wait_if_open()  # blocks until cooldown elapses
    assert time.monotonic() - start >= 0.1 - 0.01
    assert not breaker.is_open()


@pytest.mark.unit
def test_breaker_success_resets_consecutive_count():
    breaker = CircuitBreaker(failure_threshold=3, base_cooldown=99.0)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()  # reset
    assert breaker.record_failure() is None  # only 1 consecutive again
    assert not breaker.is_open()


@pytest.mark.unit
def test_breaker_cooldown_escalates_on_repeated_trips():
    breaker = CircuitBreaker(
        failure_threshold=1,
        base_cooldown=0.05,
        max_cooldown=10.0,
        cooldown_factor=2.0,
    )
    first = breaker.record_failure()  # trip 1
    breaker.wait_if_open()
    second = breaker.record_failure()  # trip 2
    assert first == pytest.approx(0.05)
    assert second == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Retry-After handling in _request_with_retry
# ---------------------------------------------------------------------------


def _http_error_resp(status: int, retry_after: str | None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {"Retry-After": retry_after} if retry_after is not None else {}
    err = requests.HTTPError(f"{status}")
    err.response = resp
    fake = MagicMock()
    fake.raise_for_status.side_effect = err
    return fake


@pytest.mark.unit
def test_retry_after_header_is_honored():
    throttled = _http_error_resp(429, "5")
    ok = MagicMock()
    ok.raise_for_status.return_value = None
    session = MagicMock()
    session.get.side_effect = [throttled, ok]

    with patch.object(wayback.time, "sleep") as m_sleep:
        resp = wayback._request_with_retry(session, "https://ia/x")

    assert resp is ok
    # The single backoff sleep must be at least the Retry-After value (5s).
    assert m_sleep.call_count == 1
    assert m_sleep.call_args.args[0] >= 5.0


@pytest.mark.unit
def test_retry_after_ignored_when_not_throttle_status():
    assert wayback._retry_after_seconds(_error_from(_http_error_resp(500, "9"))) is None
    assert wayback._retry_after_seconds(_error_from(_http_error_resp(429, "3"))) == 3.0
    # HTTP-date form is unsupported → None (falls back to backoff).
    assert (
        wayback._retry_after_seconds(
            _error_from(_http_error_resp(503, "Wed, 21 Oct 2099 07:28:00 GMT"))
        )
        is None
    )


def _error_from(fake_resp) -> requests.RequestException:
    try:
        fake_resp.raise_for_status()
    except requests.HTTPError as exc:
        return exc
    raise AssertionError("expected HTTPError")


# ---------------------------------------------------------------------------
# Breaker wired into the transport
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_connection_refused_records_breaker_failure():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("[Errno 61] Connection refused")
    breaker = MagicMock()
    breaker.record_failure.return_value = None

    with patch.object(wayback.time, "sleep"):
        out = wayback._request_with_retry(session, "https://ia/x", breaker=breaker)

    assert out is None
    # One record_failure per attempt, never a success.
    assert breaker.record_failure.call_count == wayback._RETRY_ATTEMPTS
    breaker.record_success.assert_not_called()


@pytest.mark.unit
def test_success_records_breaker_success():
    ok = MagicMock()
    ok.raise_for_status.return_value = None
    session = MagicMock()
    session.get.return_value = ok
    breaker = MagicMock()

    wayback._request_with_retry(session, "https://ia/x", breaker=breaker)
    breaker.record_success.assert_called_once()
    breaker.record_failure.assert_not_called()


@pytest.mark.unit
def test_breaker_wait_if_open_called_before_each_attempt():
    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("refused")
    breaker = MagicMock()
    breaker.record_failure.return_value = None

    with patch.object(wayback.time, "sleep"):
        wayback._request_with_retry(session, "https://ia/x", breaker=breaker)

    assert breaker.wait_if_open.call_count == wayback._RETRY_ATTEMPTS


# ---------------------------------------------------------------------------
# Session reuse in run_source_backfill
# ---------------------------------------------------------------------------


def _write_universe(source_dir: Path, urls: list[str]) -> None:
    raw = source_dir / "raw_items"
    raw.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"url": u, "url_hash": f"h{i}", "currency": "USD"})
        for i, u in enumerate(urls)
    ]
    (raw / "run.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.unit
def test_worker_reuses_one_session_across_urls(tmp_path: Path):
    urls = [f"https://x.test/p/{i}" for i in range(5)]
    _write_universe(tmp_path, urls)
    bulk = {f"h{i}": ["20240101000000"] for i in range(5)}

    made: list[MagicMock] = []

    def fake_make_session(**_):
        s = MagicMock()
        made.append(s)
        return s

    with (
        patch("prices.backfill.make_session", side_effect=fake_make_session),
        patch("prices.backfill.get_selectors", return_value={}),
        patch("prices.backfill._load_spider_parse_html", return_value=None),
        patch("prices.backfill.bulk_discover", return_value=bulk),
        patch("prices.backfill.fetch_snapshot", return_value=None) as m_fetch,
    ):
        stats = backfill.run_source_backfill(
            source_dir=tmp_path,
            spider="dummy",
            workers=1,
            requests_per_second=0,  # disable pacing for a fast test
        )

    assert stats["urls_total"] == 5
    # 1 discovery session + exactly 1 pooled worker session (not 1-per-URL).
    assert len(made) == 2
    # fetch_snapshot called once per URL, proving all 5 rode the same session.
    assert m_fetch.call_count == 5
    # Every created session was closed at run end.
    for s in made:
        s.close.assert_called_once()
