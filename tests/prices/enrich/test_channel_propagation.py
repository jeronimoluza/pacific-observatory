"""Channel propagation through concatenate → prepare → cluster_id."""
from __future__ import annotations

import pandas as pd

from prices.enrich.tier_b import index as tier_b_index
from prices.enrich.stages.prepare import prepare_input
from prices.enrich.stages.tier_c import _priors_for


def _row(country="japan", source="emart_kr", channel="supermarket", name="rice 5kg"):
    return {
        "url_hash": "h" + name.replace(" ", ""),
        "product_name": name,
        "price": 100.0,
        "currency": "USD",
        "country": country,
        "source": source,
        "date": "2026-01-01",
        "product_url": "https://x",
        "product_id": "p1",
        "region": "eap",
        "subregion": "east_asia",
        "wayback": False,
        "channel": channel,
        "category": "Pantry > Rice",
    }


def test_prepare_carries_channel_through_groupby():
    df = pd.DataFrame(
        [
            _row(name="rice 5kg", channel="supermarket"),
            _row(name="rice 5kg", channel="supermarket"),  # same product, dedup
            _row(name="bandage", channel="pharmacy"),
        ]
    )
    out = prepare_input(df)
    assert "channel" in out.columns
    # both supermarket rows collapse into one input_hash group.
    assert sorted(out["channel"].tolist()) == ["pharmacy", "supermarket"]


def test_prepare_preserves_category_breadcrumb():
    df = pd.DataFrame([_row(name="rice 5kg")])
    out = prepare_input(df)
    assert "category" in out.columns
    assert out["category"].iloc[0] == "Pantry > Rice"


def test_prepare_modal_channel_on_ambiguous_input():
    """When the same input_hash appears with different channels (genuinely
    cross-channel product), the modal channel wins after groupby."""
    df = pd.DataFrame(
        [
            _row(name="aspirin", channel="pharmacy"),
            _row(name="aspirin", channel="pharmacy"),
            _row(name="aspirin", channel="supermarket"),
        ]
    )
    out = prepare_input(df)
    # Modal of [pharmacy, pharmacy, supermarket] = pharmacy.
    assert out["channel"].iloc[0] == "pharmacy"


def test_prepare_handles_missing_channel():
    df = pd.DataFrame([_row(channel="")])
    out = prepare_input(df)
    assert out["channel"].iloc[0] == ""


def test_cluster_cache_keys_by_channel():
    """Same canonical_strict across two channels = two clusters."""
    cache = pd.DataFrame(
        [
            {
                "product_name_original": "Aspirin 100mg",
                "country": "japan",
                "channel": "pharmacy",
                "canonical_strict": "aspirin",
                "coicop_code": "06.1.1.1",
                "sub_label_id": "aspirin",
                "state": "resolved",
            },
            {
                "product_name_original": "Aspirin 100mg",
                "country": "japan",
                "channel": "supermarket",
                "canonical_strict": "aspirin",
                "coicop_code": "01.1.1.1",  # different COICOP — cross-channel contamination would mask this
                "sub_label_id": "aspirin",
                "state": "resolved",
            },
        ]
    )
    clusters = tier_b_index.cluster_cache(cache)
    assert len(clusters) == 2
    cluster_ids = sorted(clusters["cluster_id"].tolist())
    assert cluster_ids[0] == "japan::pharmacy::aspirin"
    assert cluster_ids[1] == "japan::supermarket::aspirin"


def test_cluster_cache_treats_missing_channel_as_null_partition():
    cache = pd.DataFrame(
        [
            {
                "product_name_original": "Aspirin 100mg",
                "country": "japan",
                "canonical_strict": "aspirin",
                "coicop_code": "06.1.1.1",
                "sub_label_id": "aspirin",
                "state": "resolved",
            },
        ]
    )
    clusters = tier_b_index.cluster_cache(cache)
    assert len(clusters) == 1
    assert clusters["cluster_id"].iloc[0] == "japan::null::aspirin"
    assert clusters["channel"].iloc[0] == "null"


def test_channel_priors_loaded_for_known_channels():
    assert _priors_for("pharmacy") == ["05", "06", "12"]
    assert _priors_for("supermarket") == ["01", "02", "05", "09", "12"]
    assert _priors_for("fuel-station") == ["04", "07"]
    # Empty priors = no narrowing.
    assert _priors_for("aggregator") == []
    assert _priors_for("hypermarket") == []
    assert _priors_for(None) == []
    assert _priors_for("") == []


def test_channel_priors_unknown_channel_returns_empty():
    assert _priors_for("nonexistent-channel") == []
