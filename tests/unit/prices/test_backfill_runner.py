"""Unit tests for per-URL backfill runner."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from prices.backfill import Ledger, backfill_one_url


SELECTORS = {
    "product_name": ["h1.t::text"],
    "price": ["span.p::text"],
    "category": ["a.c::text"],
}

HTML_OK = (
    '<html><h1 class="t">Widget</h1>'
    '<span class="p">$9.99</span>'
    '<a class="c">Cat</a></html>'
)
HTML_NO_PRICE = '<html><h1 class="t">Widget</h1><a class="c">Cat</a></html>'


@pytest.mark.unit
def test_backfill_one_url_emits_rows_with_wayback_metadata(tmp_path: Path):
    ledger = Ledger(tmp_path / ".ledger.json")

    with (
        patch(
            "prices.backfill.discover_snapshots",
            return_value=["20240101000000", "20240202000000"],
        ),
        patch("prices.backfill.fetch_snapshot", return_value=HTML_OK),
    ):
        rows = backfill_one_url(
            session=object(),
            url="https://x.test/widget",
            url_hash="hhh",
            cutoff=date(2023, 1, 1),
            selectors=SELECTORS,
            ledger=ledger,
            currency="USD",
            collapse_digits=8,
        )

    assert len(rows) == 2
    first = rows[0]
    assert first["url"] == "https://x.test/widget"
    assert first["url_hash"] == "hhh"
    assert first["product_name"] == "Widget"
    assert first["price"] == "$9.99"
    assert first["currency"] == "USD"
    assert first["source_kind"] == "wayback"
    assert first["wayback_timestamp"] == "20240101000000"
    assert first["scraped_at_utc"] == "2024-01-01T00:00:00+00:00"
    assert ledger.is_done("hhh", "20240101000000")
    assert ledger.is_done("hhh", "20240202000000")


@pytest.mark.unit
def test_backfill_one_url_drops_rows_with_no_price_but_records_ledger(tmp_path: Path):
    ledger = Ledger(tmp_path / ".ledger.json")

    with (
        patch("prices.backfill.discover_snapshots", return_value=["20240101000000"]),
        patch("prices.backfill.fetch_snapshot", return_value=HTML_NO_PRICE),
    ):
        rows = backfill_one_url(
            session=object(),
            url="https://x.test/widget",
            url_hash="hhh",
            cutoff=date(2023, 1, 1),
            selectors=SELECTORS,
            ledger=ledger,
            currency="USD",
        )

    assert rows == []
    assert ledger.is_done("hhh", "20240101000000")


@pytest.mark.unit
def test_backfill_one_url_skips_timestamps_in_ledger(tmp_path: Path):
    ledger = Ledger(tmp_path / ".ledger.json")
    ledger.record("hhh", "20240101000000")

    with (
        patch(
            "prices.backfill.discover_snapshots",
            return_value=["20240101000000", "20240202000000"],
        ),
        patch("prices.backfill.fetch_snapshot", return_value=HTML_OK) as m_fetch,
    ):
        rows = backfill_one_url(
            session=object(),
            url="https://x.test/widget",
            url_hash="hhh",
            cutoff=date(2023, 1, 1),
            selectors=SELECTORS,
            ledger=ledger,
            currency="USD",
        )

    assert len(rows) == 1
    assert rows[0]["wayback_timestamp"] == "20240202000000"
    assert m_fetch.call_count == 1


@pytest.mark.unit
def test_backfill_one_url_respects_max_snapshots(tmp_path: Path):
    ledger = Ledger(tmp_path / ".ledger.json")
    tss = [f"2024{m:02d}01000000" for m in range(1, 13)]

    with (
        patch("prices.backfill.discover_snapshots", return_value=tss),
        patch("prices.backfill.fetch_snapshot", return_value=HTML_OK) as m_fetch,
    ):
        rows = backfill_one_url(
            session=object(),
            url="https://x.test/widget",
            url_hash="hhh",
            cutoff=date(2023, 1, 1),
            selectors=SELECTORS,
            ledger=ledger,
            currency="USD",
            max_snapshots=3,
        )

    assert len(rows) == 3
    assert m_fetch.call_count == 3
