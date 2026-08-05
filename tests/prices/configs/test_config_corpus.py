"""Whole-corpus invariants over src/prices/configs/**/*.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
import yaml

from prices.enrich.schemas import Channel

CONFIGS = Path(__file__).resolve().parents[3] / "src" / "prices" / "configs"

RETIRED_CHANNELS = {"aggregator", "mixed"}


def _manifests():
    for path in sorted(CONFIGS.rglob("*.yaml")):
        if "_examples" in path.parts:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            yield path, data


def test_corpus_is_non_trivial():
    assert sum(1 for _ in _manifests()) >= 300


@pytest.mark.parametrize(
    "path,data", list(_manifests()), ids=lambda x: getattr(x, "stem", "")
)
def test_channel_is_valid_or_null(path, data):
    channel = data.get("channel", "__missing__")
    assert channel != "__missing__", f"{path}: channel key is required"
    assert channel is None or channel in get_args(
        Channel
    ), f"{path}: bad channel {channel!r}"


def test_no_retired_channel_values_anywhere():
    offenders = [
        str(path)
        for path, data in _manifests()
        if data.get("channel") in RETIRED_CHANNELS
    ]
    assert offenders == []


def test_no_retired_channel_named_in_prose():
    """A retired value must not survive in notes/comments either — stale prose
    misleads the next person auditing a source."""
    offenders = []
    for path in sorted(CONFIGS.rglob("*.yaml")):
        if "_examples" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED_CHANNELS:
            if f"channel={retired}" in text or f"channel: {retired}" in text:
                offenders.append(f"{path}: {retired}")
    assert offenders == []
