"""Unit tests for backfill ledger I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prices.backfill import Ledger


@pytest.mark.unit
def test_ledger_load_empty_when_file_missing(tmp_path: Path):
    led = Ledger.load(tmp_path / "wayback_items" / ".ledger.json")
    assert led.is_done("aaa", "20240101000000") is False


@pytest.mark.unit
def test_ledger_record_and_save_then_reload(tmp_path: Path):
    path = tmp_path / "wayback_items" / ".ledger.json"
    led = Ledger.load(path)
    led.record("aaa", "20240101000000")
    led.record("aaa", "20240202000000")
    led.record("bbb", "20240101000000")
    led.save()

    assert path.exists()
    data = json.loads(path.read_text())
    assert sorted(data["aaa"]) == ["20240101000000", "20240202000000"]
    assert data["bbb"] == ["20240101000000"]

    reloaded = Ledger.load(path)
    assert reloaded.is_done("aaa", "20240101000000") is True
    assert reloaded.is_done("aaa", "20240202000000") is True
    assert reloaded.is_done("bbb", "20240101000000") is True
    assert reloaded.is_done("ccc", "20240101000000") is False


@pytest.mark.unit
def test_ledger_record_is_idempotent(tmp_path: Path):
    path = tmp_path / ".ledger.json"
    led = Ledger.load(path)
    led.record("aaa", "20240101000000")
    led.record("aaa", "20240101000000")
    led.save()
    assert json.loads(path.read_text())["aaa"] == ["20240101000000"]
