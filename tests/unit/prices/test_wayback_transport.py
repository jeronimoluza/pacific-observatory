"""Unit tests for src/prices/_shared/wayback.py."""

from __future__ import annotations

import hashlib
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from prices._shared import wayback


@pytest.mark.unit
def test_discover_snapshots_parses_cdx_rows_and_filters_by_cutoff():
    fake_resp = MagicMock()
    fake_resp.json.return_value = [
        ["timestamp", "statuscode", "mimetype"],
        ["20230115120000", "200", "text/html"],
        ["20230201090000", "200", "text/html"],
        ["20240620000000", "200", "text/html"],
    ]
    fake_resp.raise_for_status.return_value = None

    session = MagicMock()
    session.get.return_value = fake_resp

    out = wayback.discover_snapshots(
        session, "https://example.com/p/1", date(2023, 1, 1), collapse_digits=8
    )

    assert out == ["20230115120000", "20230201090000", "20240620000000"]
    call_kwargs = session.get.call_args.kwargs
    assert call_kwargs["params"]["url"] == "https://example.com/p/1"
    assert call_kwargs["params"]["collapse"] == "timestamp:8"
    assert call_kwargs["params"]["from"] == "20230101"


@pytest.mark.unit
def test_discover_snapshots_returns_empty_on_empty_cdx():
    fake_resp = MagicMock()
    fake_resp.json.return_value = [["timestamp", "statuscode", "mimetype"]]
    fake_resp.raise_for_status.return_value = None

    session = MagicMock()
    session.get.return_value = fake_resp

    out = wayback.discover_snapshots(
        session, "https://example.com/p/2", date(2020, 1, 1)
    )
    assert out == []


@pytest.mark.unit
def test_discover_snapshots_returns_empty_on_request_failure():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("boom")

    out = wayback.discover_snapshots(
        session, "https://example.com/p/3", date(2024, 1, 1)
    )
    assert out == []


@pytest.mark.unit
def test_fetch_snapshot_returns_text_on_success():
    fake_resp = MagicMock()
    fake_resp.text = "<html>p</html>"
    fake_resp.raise_for_status.return_value = None

    session = MagicMock()
    session.get.return_value = fake_resp

    out = wayback.fetch_snapshot(session, "20240101000000", "https://example.com/p/1")
    assert out == "<html>p</html>"
    fetched_url = session.get.call_args.args[0]
    assert fetched_url == (
        "https://web.archive.org/web/20240101000000id_/https://example.com/p/1"
    )


@pytest.mark.unit
def test_fetch_snapshot_returns_none_on_failure():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("slow")

    out = wayback.fetch_snapshot(session, "20240101000000", "https://example.com/p/2")
    assert out is None


@pytest.mark.unit
def test_parse_timestamp_to_date():
    assert wayback.parse_timestamp_to_date("20240102030405") == date(2024, 1, 2)
    assert wayback.parse_timestamp_to_date("abc") is None
    assert wayback.parse_timestamp_to_date("99999999") is None


@pytest.mark.unit
def test_collapse_timestamps_buckets_and_keeps_earliest():
    # Mon + Tue of ISO week 1, then week 2, a later month, a later year.
    ts = [
        "20240102080000",  # Tue, ISO 2024-W01
        "20240101120000",  # Mon, ISO 2024-W01 (earlier)
        "20240108090000",  # Mon, ISO 2024-W02
        "20240201000000",
        "20250101000000",
    ]
    assert wayback.collapse_timestamps(ts, "week") == [
        "20240101120000",
        "20240108090000",
        "20240201000000",
        "20250101000000",
    ]
    assert wayback.collapse_timestamps(ts, "month") == [
        "20240101120000",
        "20240201000000",
        "20250101000000",
    ]
    assert wayback.collapse_timestamps(ts, "year") == [
        "20240101120000",
        "20250101000000",
    ]


@pytest.mark.unit
def test_derive_scopes_tightens_single_tenant_and_groups_by_host():
    urls = [
        "https://shop.cosmed.com.tw/SalePage/Index/123",
        "https://shop.cosmed.com.tw/SalePage/Index/999",
        "https://item.rakuten.co.jp/shopA/xyz/",
        "https://item.rakuten.co.jp/shopB/abc/",
    ]
    scopes = dict(wayback._derive_scopes(urls))
    assert scopes["shop.cosmed.com.tw/SalePage/Index/"] == "prefix"
    assert scopes["item.rakuten.co.jp/"] == "prefix"


@pytest.mark.unit
def test_iter_bulk_captures_pages_until_empty():
    page0 = MagicMock()
    page0.json.return_value = [
        ["original", "timestamp"],
        ["https://x.test/a", "20240101000000"],
        ["https://x.test/b", "20240108000000"],
    ]
    page0.raise_for_status.return_value = None
    page1 = MagicMock()  # empty → past the end, stop
    page1.json.return_value = [["original", "timestamp"]]
    page1.raise_for_status.return_value = None

    session = MagicMock()
    session.get.side_effect = [page0, page1]

    out = list(
        wayback.iter_bulk_captures(session, "x.test/", "prefix", date(2020, 1, 1))
    )
    assert out == [
        ("https://x.test/a", "20240101000000"),
        ("https://x.test/b", "20240108000000"),
    ]
    # page 0 then page 1 (empty) → exactly 2 requests, no showNumPages probe
    assert session.get.call_count == 2
    assert session.get.call_args_list[0].kwargs["params"]["page"] == 0
    assert session.get.call_args_list[1].kwargs["params"]["page"] == 1


@pytest.mark.unit
def test_bulk_discover_intersects_universe_and_collapses(monkeypatch):
    universe = [
        {"url": "https://x.test/a", "url_hash": "AA"},
        {"url": "https://x.test/b/", "url_hash": "BB"},  # trailing slash variant
    ]

    def fake_iter(session, scope, match_type, cutoff, *, timeout=60):
        yield ("http://x.test/a", "20240101000000")  # week 1 (scheme differs)
        yield ("https://x.test/a", "20240102000000")  # week 1 → collapsed away
        yield ("https://x.test/b", "20240108000000")  # matches BB despite slash
        yield ("https://x.test/unknown", "20240101000000")  # not in universe

    monkeypatch.setattr(wayback, "iter_bulk_captures", fake_iter)

    buckets, discovered = wayback.bulk_discover(MagicMock(), universe, date(2020, 1, 1))
    assert buckets == {"AA": ["20240101000000"], "BB": ["20240108000000"]}
    assert discovered == []


@pytest.mark.unit
def test_bulk_discover_matches_when_only_the_query_string_differs(monkeypatch):
    """Storefronts serve /p/foo?variant=1; Wayback archives /p/foo."""
    universe = [
        {"url": "https://x.test/p/foo?variant=123", "url_hash": "AA"},
        {"url": "https://x.test/p/bar?variant=9", "url_hash": "BB"},
    ]

    def fake_iter(session, scope, match_type, cutoff, *, timeout=60):
        yield ("https://x.test/p/foo", "20240101000000")  # canonical, no query
        yield ("https://x.test/p/bar?variant=9", "20240108000000")  # exact match

    monkeypatch.setattr(wayback, "iter_bulk_captures", fake_iter)

    buckets, discovered = wayback.bulk_discover(MagicMock(), universe, date(2020, 1, 1))
    assert buckets == {"AA": ["20240101000000"], "BB": ["20240108000000"]}
    assert discovered == []


@pytest.mark.unit
def test_bulk_discover_archive_universe_keeps_never_scraped_urls(monkeypatch):
    universe = [{"url": "https://x.test/p/a", "url_hash": "AA"}]

    def fake_iter(session, scope, match_type, cutoff, *, timeout=60):
        yield ("https://x.test/p/a", "20240101000000")
        yield ("https://x.test/p/delisted", "20180101000000")  # gone before we scraped
        yield ("https://x.test/category/food", "20180101000000")  # not a product page

    monkeypatch.setattr(wayback, "iter_bulk_captures", fake_iter)

    buckets, discovered = wayback.bulk_discover(
        MagicMock(),
        universe,
        date(2010, 1, 1),
        include_unmatched=True,
        scope_prefix="x.test/",
        path_re=r"^/p/[^/]+$",
    )

    assert len(discovered) == 1
    entry = discovered[0]
    assert entry["url"] == "https://x.test/p/delisted"
    assert entry["url_hash"] == hashlib.md5(entry["url"].encode()).hexdigest()
    assert entry["earliest_scraped_at"] is None
    # The category page was filtered out by path_re; the delisted product wasn't.
    assert buckets[entry["url_hash"]] == ["20180101000000"]
    assert buckets["AA"] == ["20240101000000"]
    assert len(buckets) == 2


@pytest.mark.unit
def test_bulk_discover_scope_prefix_overrides_the_scraped_set(monkeypatch):
    """Archive mode must not let the scraped set bound the CDX query."""
    universe = [{"url": "https://x.test/p/deep/nested/only-one", "url_hash": "AA"}]
    seen: list[str] = []

    def fake_iter(session, scope, match_type, cutoff, *, timeout=60):
        seen.append(scope)
        return iter(())

    monkeypatch.setattr(wayback, "iter_bulk_captures", fake_iter)

    wayback.bulk_discover(MagicMock(), universe, date(2010, 1, 1))
    assert seen == ["x.test/p/deep/nested/"]  # LCP of the scraped set

    seen.clear()
    wayback.bulk_discover(
        MagicMock(), universe, date(2010, 1, 1), scope_prefix="x.test/p/"
    )
    assert seen == ["x.test/p/"]
