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


def test_no_config_narrow_short_circuits_to_a_non_leaf():
    """Whole-corpus regression for the ADR-0002 narrow short-circuit defect:
    a source whose `coicop_codes` share a single class prefix used to bypass
    the classifier and stamp the (possibly non-leaf) resolved code verbatim.
    `coicop_codes.is_narrow` now gates on leafness, so no config in the corpus
    may resolve `is_narrow(...) is True` to anything but an actual taxonomy
    leaf -- and the set of sources that DO narrow is pinned so it cannot grow
    silently (i.e. so a new source can't quietly regain the wrong-code path).
    """
    from prices.config import PriceSourceConfig, discover_prices_configs
    from prices.enrich import coicop_codes
    from prices.enrich.coicop_taxonomy import load_taxonomy_index

    leaves, _ = load_taxonomy_index()
    narrowed = set()
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if not cfg.coicop_codes:
            continue
        if coicop_codes.is_narrow(cfg.coicop_codes, leaves):
            resolved = coicop_codes.resolved_code(cfg.coicop_codes)
            assert resolved in leaves, f"{path}: {resolved!r} is not a leaf"
            narrowed.add(cfg.source)

    # Pinned 2026-09-03: exactly these 33 sources declare a single real leaf
    # code. Adding a new one here must be a deliberate review, not a silent
    # side effect of a config edit -- update this set only after confirming
    # the new source's resolved code really is a leaf. Grew from 4 to 33 the
    # same day: 69 manifests declared a prefix one dotted segment short of its
    # leaf (e.g. "04.1.1" instead of "04.1.1.0"), which used to silently drop
    # every one of their observations at classify time; those YAMLs were
    # corrected to the actual leaf. `eurostat_electricity` alone covers 33
    # per-country manifests that all share that one file stem as `source`.
    expected = {
        "dailynk",
        "air_vanuatu_domestic",
        "pakwheels_pk",
        "snel_cd",
        "anjuke",
        "batdongsan_vn",
        "bel_tariff",
        "bpl_fuel_charge_bs",
        "cafe_letefoho",
        "ceb_electricity_tariff",
        "cie_tariff",
        "ddproperty_th",
        "denner_ch",
        "ebs_tariff",
        "emae_electricity_tariff",
        "era_electricity_tariff",
        "ethiopiapropertycentre_et",
        "eurostat_electricity",
        "evn_vn_tariff",
        "lamudi_ph",
        "laoproperties",
        "lkw_stromtarife",
        "mogi_vn",
        "mubawab_ma",
        "propertyguru_my",
        "propertyguru_sg",
        "seeg_electricity_tariff_ga",
        "siea_tariff",
        "sp_group_tariff",
        "telia_no",
        "ura_electricity_tariff",
        "yspsc_electricity_tariff",
        "yula",
    }
    assert narrowed == expected


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
