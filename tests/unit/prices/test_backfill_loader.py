"""Unit tests for backfill URL-universe loader."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from prices.backfill import load_url_universe


@pytest.mark.unit
def test_load_url_universe_unions_jsonl_files_and_dedupes(tmp_path: Path):
    raw_dir = tmp_path / "raw_items"
    raw_dir.mkdir()

    older = [
        {
            "url": "https://x.test/a",
            "url_hash": "aaa",
            "scraped_at_utc": "2024-03-01T00:00:00+00:00",
        },
        {
            "url": "https://x.test/b",
            "url_hash": "bbb",
            "scraped_at_utc": "2024-03-01T00:00:00+00:00",
        },
    ]
    newer = [
        {
            "url": "https://x.test/a",
            "url_hash": "aaa",
            "scraped_at_utc": "2025-01-01T00:00:00+00:00",
        },
        {
            "url": "https://x.test/c",
            "url_hash": "ccc",
            "scraped_at_utc": "2025-01-01T00:00:00+00:00",
        },
    ]
    (raw_dir / "src_20240301_000000.jsonl").write_text(
        "\n".join(json.dumps(r) for r in older) + "\n"
    )
    (raw_dir / "src_20250101_000000.jsonl").write_text(
        "\n".join(json.dumps(r) for r in newer) + "\n"
    )

    rows = load_url_universe(tmp_path)

    assert len(rows) == 3
    by_hash = {r["url_hash"]: r for r in rows}
    assert by_hash["aaa"]["earliest_scraped_at"] == datetime(
        2024, 3, 1, tzinfo=timezone.utc
    )
    assert by_hash["aaa"]["url"] == "https://x.test/a"
    assert by_hash["ccc"]["earliest_scraped_at"] == datetime(
        2025, 1, 1, tzinfo=timezone.utc
    )


@pytest.mark.unit
def test_load_url_universe_skips_rows_missing_url_or_hash(tmp_path: Path):
    raw_dir = tmp_path / "raw_items"
    raw_dir.mkdir()
    rows = [
        {"url_hash": "x"},
        {"url": "https://x.test/no-hash"},
        {
            "url": "https://x.test/ok",
            "url_hash": "ok",
            "scraped_at_utc": "2025-01-01T00:00:00+00:00",
        },
    ]
    (raw_dir / "src.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = load_url_universe(tmp_path)
    assert [r["url_hash"] for r in out] == ["ok"]


@pytest.mark.unit
def test_load_url_universe_empty_when_no_raw_items(tmp_path: Path):
    assert load_url_universe(tmp_path) == []
