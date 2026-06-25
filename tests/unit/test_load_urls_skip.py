"""Tests for memory-bounded resume loading of urls.csv (skip_urls filter)."""

from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

pytestmark = pytest.mark.unit


def _write_urls_csv(newspaper_dir: Path) -> None:
    (newspaper_dir / "urls.csv").write_text(
        "url,title,date\n"
        "https://ex.com/a,Article A,2024-01-01\n"
        "https://ex.com/b,Article B,2024-01-02\n"
        "https://ex.com/c,Article C,2024-01-03\n"
        "https://ex.com,Root,2024-01-04\n",  # normalizes to https://ex.com/
        encoding="utf-8",
    )


def test_load_without_skip_returns_all_rows():
    from text.scrapers.pipelines.storage.urls import URLTracker

    with tempfile.TemporaryDirectory() as d:
        nd = Path(d)
        _write_urls_csv(nd)
        records = URLTracker(nd.parent).load_urls_from_csv(nd)
        assert records is not None
        assert len(records) == 4


def test_skip_urls_drops_matching_and_uses_normalized_key():
    from text.scrapers.pipelines.storage.urls import URLTracker

    with tempfile.TemporaryDirectory() as d:
        nd = Path(d)
        _write_urls_csv(nd)
        # 'https://ex.com/' is the normalized form of the bare-root row, proving
        # the skip match is computed on str(ThumbnailRecord.url), not the raw cell.
        skip = {"https://ex.com/a", "https://ex.com/"}
        pending = URLTracker(nd.parent).load_urls_from_csv(nd, skip_urls=skip)
        assert sorted(str(t.url) for t in pending) == [
            "https://ex.com/b",
            "https://ex.com/c",
        ]


def test_skip_filter_spans_chunk_boundaries(monkeypatch):
    from text.scrapers.pipelines.storage import urls as urls_mod
    from text.scrapers.pipelines.storage.urls import URLTracker

    monkeypatch.setattr(urls_mod, "URLS_LOAD_CHUNKSIZE", 1)
    with tempfile.TemporaryDirectory() as d:
        nd = Path(d)
        _write_urls_csv(nd)
        skip = {"https://ex.com/a", "https://ex.com/"}
        pending = URLTracker(nd.parent).load_urls_from_csv(nd, skip_urls=skip)
        assert sorted(str(t.url) for t in pending) == [
            "https://ex.com/b",
            "https://ex.com/c",
        ]


def test_missing_file_returns_none():
    from text.scrapers.pipelines.storage.urls import URLTracker

    with tempfile.TemporaryDirectory() as d:
        nd = Path(d)
        assert URLTracker(nd.parent).load_urls_from_csv(nd, skip_urls={"x"}) is None
