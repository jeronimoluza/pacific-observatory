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


DECLARED_ELSEWHERE = {"region", "subregion", "country", "source", "config_path"}


def test_no_manifest_key_is_silently_dropped():
    """Every key used anywhere in the corpus must be a declared model field."""
    from prices.config import PriceSourceConfig

    fields = set(PriceSourceConfig.model_fields) | DECLARED_ELSEWHERE
    used: set[str] = set()
    for _, data in _manifests():
        used |= set(data)
    assert used - fields == set()


def test_unknown_keys_are_rejected():
    from pydantic import ValidationError
    from prices.config import PriceSourceConfig

    with pytest.raises(ValidationError):
        PriceSourceConfig.model_validate(
            {
                "scaffolding": "spider",
                "spider": "x",
                "channel": None,
                "region": "r",
                "subregion": "s",
                "country": "c",
                "source": "t",
                "config_path": "/tmp/t.yaml",
                "typoed_key": 1,
            }
        )
