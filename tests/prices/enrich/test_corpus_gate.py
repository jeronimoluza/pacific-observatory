"""The corpus gate selects fetcher manifests whose COICOP is assigned downstream.

Renaming the marker value must not change *which* manifests are selected — that
set decides which fetcher CSVs reach the classifier (wholesale live-animal feeds
among them). A miss here fails silently: the gate simply matches nothing.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from prices.enrich.stages.concatenate import (
    CLASSIFIER_MARKER,
    _build_classifier_csv_map,
)

CONFIGS = Path(__file__).resolve().parents[3] / "src" / "prices" / "configs"

# Frozen expectation, captured before the 2026-08-05 marker rename.
# Adding a source here is a deliberate act: confirm the new entry against
# _build_classifier_csv_map() output and that the source genuinely belongs in
# the classifier corpus. Do not append merely to make this assertion pass —
# an unexpected key may mean a manifest was mis-tagged, not that the corpus grew.
EXPECTED_KEYS = {
    ("hong_kong_sar_china", "afcd_wholesale"),
    ("taiwan_china", "moa_wholesale"),
    ("singapore", "singstat_arp"),
    ("thailand", "talaadthai"),
}


def test_gate_selects_exactly_the_known_fetcher_manifests():
    assert set(_build_classifier_csv_map()) == EXPECTED_KEYS


def test_gate_count_matches_a_fresh_yaml_scan():
    """Independent recount straight from disk — catches a stale module cache."""
    n = 0
    for path in CONFIGS.rglob("*.yaml"):
        if "_examples" in path.parts:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if (
            data.get("coicop_classification") == CLASSIFIER_MARKER
            and data.get("scaffolding") == "fetcher"
        ):
            n += 1
    assert n == len(EXPECTED_KEYS)


def test_wholesale_feeds_carry_their_channel():
    """The map's value is the channel string handed to the corpus."""
    mapping = _build_classifier_csv_map()
    assert mapping[("taiwan_china", "moa_wholesale")] == "wholesale"
    assert mapping[("hong_kong_sar_china", "afcd_wholesale")] == "wholesale"
    assert mapping[("thailand", "talaadthai")] == "wholesale"
