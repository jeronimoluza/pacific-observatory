"""Region-restricted builds (`prices publish --region eap --out ...`).

The restriction has to happen before the aggregations run, not after, so the
snapshot, the monthly series, the region/World medians and the low-coverage
cutoff are all computed over the same country set that ends up on screen.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from prices import publish

REGIONS = (
    {"fiji": "eap", "tonga": "eap", "peru": "lac"},
    [
        {"key": "eap", "label": "East Asia & Pacific"},
        {"key": "lac", "label": "Latin America & Caribbean"},
    ],
)


def _current(rows):
    return pd.DataFrame(
        [
            {
                "coicop_code": code,
                "country": country,
                "standard_unit": "kg",
                "median_usd": v,
                "n_obs": 10,
                "last_seen": pd.Timestamp("2026-09-01"),
            }
            for code, country, v in rows
        ]
    )


@pytest.mark.unit
def test_payload_region_cols_drops_world_and_other_regions(monkeypatch):
    """A region build ships only its own column -- no World, no sibling regions.

    Showing "World" here would be a genuine lie: the frame has already had
    every non-EAP row filtered out by `publish`, so a "World" figure would
    just be the EAP median wearing a bigger label.
    """
    monkeypatch.setattr(publish, "_load_coicop_titles", lambda: {})
    monkeypatch.setattr(publish, "_load_country_names", lambda: {})
    monkeypatch.setattr(publish, "_load_regions", lambda: REGIONS)

    current = _current([("01.1.1.1", "fiji", 2.0), ("01.1.1.1", "tonga", 3.0)])
    monthly = pd.DataFrame(
        columns=[
            "coicop_code",
            "country",
            "month",
            "standard_unit",
            "median_usd",
            "n_obs",
        ]
    )
    payload = publish._payload(current, monthly, region="eap")
    assert payload["region_cols"] == [{"key": "eap", "label": "East Asia & Pacific"}]
    medians = payload["region_medians"]["01.1.1.1|kg"]
    assert set(medians) == {"eap"}
    assert "world" not in medians
    assert medians["eap"] == 2.5


@pytest.mark.unit
def test_payload_region_none_keeps_world_and_all_regions(monkeypatch):
    """Regression: the unrestricted, default build is untouched by the new arg."""
    monkeypatch.setattr(publish, "_load_coicop_titles", lambda: {})
    monkeypatch.setattr(publish, "_load_country_names", lambda: {})
    monkeypatch.setattr(publish, "_load_regions", lambda: REGIONS)

    current = _current(
        [
            ("01.1.1.1", "fiji", 2.0),
            ("01.1.1.1", "tonga", 3.0),
            ("01.1.1.1", "peru", 10.0),
        ]
    )
    monthly = pd.DataFrame(
        columns=[
            "coicop_code",
            "country",
            "month",
            "standard_unit",
            "median_usd",
            "n_obs",
        ]
    )
    payload = publish._payload(current, monthly)  # region defaults to None
    assert {c["key"] for c in payload["region_cols"]} == {"world", "eap", "lac"}
    medians = payload["region_medians"]["01.1.1.1|kg"]
    assert medians["eap"] == 2.5
    assert medians["lac"] == 10.0
    assert medians["world"] == 3.0  # median of 2, 3, 10


def _obs(rows):
    now = pd.Timestamp.now().normalize()
    return pd.DataFrame(
        [
            {
                "coicop_code": "01.1.1.1",
                "country": country,
                "unit_value_usd": v,
                "observation_date": now - pd.Timedelta(days=5),
                "standard_unit": "kg",
                "qa_status": "trusted",
            }
            for country, v in rows
        ]
    )


@pytest.mark.unit
def test_publish_region_filters_the_whole_pipeline(tmp_path, monkeypatch):
    """`publish(region=...)` restricts every downstream figure, not just columns."""
    obs = _obs([("fiji", 2.0), ("tonga", 3.0), ("peru", 10.0)])
    fake_parquet = tmp_path / "obs.parquet"
    fake_parquet.touch()  # only existence is checked; read is monkeypatched below

    monkeypatch.setattr(publish, "OBSERVATIONS_PARQUET", fake_parquet)
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: obs.copy())
    monkeypatch.setattr(publish, "_load_regions", lambda: REGIONS)
    monkeypatch.setattr(publish, "_load_coicop_titles", lambda: {})
    monkeypatch.setattr(publish, "_load_country_names", lambda: {})
    monkeypatch.setattr(publish, "TYPICAL_MASS_CSV", tmp_path / "no_typical_mass.csv")
    monkeypatch.setattr(publish, "SUPPRESSED_PARQUET", tmp_path / "suppressed.parquet")
    monkeypatch.setattr(publish, "VENDOR_CHART_JS", tmp_path / "chart.js")
    (tmp_path / "chart.js").write_text("/* stub */")

    out = tmp_path / "eap_dash.html"
    result = publish.publish(region="eap", out_path=out)
    assert result == out

    html = out.read_text()
    start = html.index("const DATA = ") + len("const DATA = ")
    payload, _ = json.JSONDecoder().raw_decode(html[start:])

    # peru (lac) never reaches the snapshot, the KPI, or the region medians.
    assert set(payload["country_names"]) == {"fiji", "tonga"}
    assert payload["kpi"]["countries"] == 2
    assert payload["region_cols"] == [{"key": "eap", "label": "East Asia & Pacific"}]
    medians = payload["region_medians"]["01.1.1.1|kg"]
    assert medians["eap"] == 2.5
    assert "world" not in medians


@pytest.mark.unit
def test_publish_unknown_region_raises(tmp_path, monkeypatch):
    obs = _obs([("fiji", 2.0)])
    fake_parquet = tmp_path / "obs.parquet"
    fake_parquet.touch()
    monkeypatch.setattr(publish, "OBSERVATIONS_PARQUET", fake_parquet)
    monkeypatch.setattr(pd, "read_parquet", lambda *_a, **_k: obs.copy())
    monkeypatch.setattr(publish, "_load_regions", lambda: REGIONS)

    with pytest.raises(ValueError, match="unknown region"):
        publish.publish(region="not-a-region", out_path=tmp_path / "out.html")
