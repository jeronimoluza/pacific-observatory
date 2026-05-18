"""Unit tests for src/prices/_shared/wayback.py."""

from __future__ import annotations

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

    out = wayback.fetch_snapshot(
        session, "20240101000000", "https://example.com/p/1"
    )
    assert out == "<html>p</html>"
    fetched_url = session.get.call_args.args[0]
    assert fetched_url == (
        "https://web.archive.org/web/20240101000000id_/https://example.com/p/1"
    )


@pytest.mark.unit
def test_fetch_snapshot_returns_none_on_failure():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("slow")

    out = wayback.fetch_snapshot(
        session, "20240101000000", "https://example.com/p/2"
    )
    assert out is None


@pytest.mark.unit
def test_parse_timestamp_to_date():
    assert wayback.parse_timestamp_to_date("20240102030405") == date(2024, 1, 2)
    assert wayback.parse_timestamp_to_date("abc") is None
    assert wayback.parse_timestamp_to_date("99999999") is None
