"""Integration tests for prices wayback transport. Hit real CDX + IA."""

from __future__ import annotations

from datetime import date

import pytest

from core.http import make_session
from prices._shared.wayback import discover_snapshots, fetch_snapshot


@pytest.mark.slow
@pytest.mark.integration
def test_discover_snapshots_for_stable_url():
    """anthropic.com homepage has many archived snapshots — should return >0."""
    session = make_session()
    out = discover_snapshots(
        session, "https://www.anthropic.com/", date(2024, 1, 1), collapse_digits=8
    )
    assert isinstance(out, list)
    assert len(out) > 0, "Expected at least one snapshot since 2024-01-01"
    assert all(len(ts) == 14 and ts.isdigit() for ts in out)


@pytest.mark.slow
@pytest.mark.integration
def test_fetch_snapshot_returns_html():
    """Pick the first timestamp from CDX and fetch it via id_/ endpoint."""
    session = make_session()
    tss = discover_snapshots(
        session, "https://www.anthropic.com/", date(2024, 1, 1), collapse_digits=8
    )
    assert tss, "discover_snapshots returned no timestamps"
    html = fetch_snapshot(session, tss[0], "https://www.anthropic.com/")
    assert html is not None
    assert "<html" in html.lower()
