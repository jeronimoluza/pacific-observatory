"""Channel enum validation on PriceSourceConfig."""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from prices.config import PriceSourceConfig
from prices.enrich.schemas import Channel


# Derived, never restated. A hand-copied list drifts: this tuple used to be
# written out by hand and silently fell out of sync when `wholesale` was added
# to the Literal. The GLOSSARY parity test covers the prose side.
VALID_CHANNELS = get_args(Channel)


def _kwargs(**extra):
    """Minimal valid PriceSourceConfig kwargs (spider scaffolding)."""
    return {
        "scaffolding": "spider",
        "spider": "x",
        "region": "eap",
        "subregion": "east_asia",
        "country": "japan",
        "source": "test",
        "config_path": "/tmp/test.yaml",
        **extra,
    }


@pytest.mark.parametrize("channel", VALID_CHANNELS)
def test_channel_enum_accepts_all_values(channel):
    cfg = PriceSourceConfig.model_validate(_kwargs(channel=channel))
    assert cfg.channel == channel


def test_channel_is_required():
    """Post-backfill (2026-06-11), every source YAML must declare `channel:`.
    Non-retail sources use `channel: null` — see prices/config.py docstring."""
    with pytest.raises(ValidationError):
        PriceSourceConfig.model_validate(_kwargs())


def test_channel_null_is_accepted():
    """`channel: null` is valid for non-retail sources (CPI/NSO/tariff)."""
    cfg = PriceSourceConfig.model_validate(_kwargs(channel=None))
    assert cfg.channel is None


def test_channel_rejects_unknown_value():
    with pytest.raises(ValidationError):
        PriceSourceConfig.model_validate(_kwargs(channel="bookstore"))


def test_channel_rejects_legacy_mixed_value():
    """`mixed` was renamed to `hypermarket`; old YAMLs must error loudly."""
    with pytest.raises(ValidationError):
        PriceSourceConfig.model_validate(_kwargs(channel="mixed"))


def test_channel_rejects_empty_string():
    with pytest.raises(ValidationError):
        PriceSourceConfig.model_validate(_kwargs(channel=""))


def test_channel_literal_is_non_empty_lowercase_strings():
    """Guards against an accidental non-string, upper-case, or duplicate member."""
    values = get_args(Channel)
    assert values
    assert len(values) == len(set(values))
    for v in values:
        assert isinstance(v, str) and v
        assert v == v.lower()
        assert " " not in v


NEW_CHANNELS = (
    "convenience",
    "fresh-market",
    "specialty-food",
    "marketplace",
    "real-estate",
    "other",
)


@pytest.mark.parametrize("channel", NEW_CHANNELS)
def test_new_channel_values_are_valid(channel):
    cfg = PriceSourceConfig.model_validate(_kwargs(channel=channel))
    assert cfg.channel == channel
