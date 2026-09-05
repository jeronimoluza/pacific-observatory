"""Tests for the simplified fuel pipeline (process.py)."""

from datetime import date
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _fuel_row(**overrides):
    from cpi.fuel_prices.constants import COLUMNS

    row: dict = {column: None for column in COLUMNS}
    row.update(
        {
            "country": "Malaysia",
            "wb_iso3": "MYS",
            "subnational_area": "National",
            "city": None,
            "fuel_family": "gasoline",
            "fuel_product": "RON95",
            "quality_group": "midgrade",
            "price_local": 2.05,
            "currency": "MYR",
            "unit": "L",
            "source_key": "my_mof_weekly_petroleum",
            "source_name": "MOF",
            "source_type": "official",
            "observation_date": "2026-01-15",
            "status": "Final",
            "observation_hash": "row-hash",
        }
    )
    row.update(overrides)
    return row


def _write_malaysia_obs(tmp_path, rows):
    obs_csv = tmp_path / "malaysia" / "my_mof_weekly_petroleum" / "observations.csv"
    obs_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(obs_csv, index=False)
    return obs_csv


def test_build_enriched_frame_returns_dataframe(tmp_path):
    """build_enriched_frame should return a non-empty DataFrame when given valid data."""
    from cpi.fuel_prices.process import build_enriched_frame

    _write_malaysia_obs(tmp_path, [_fuel_row()])

    df = build_enriched_frame(collect_dir=tmp_path)

    assert not df.empty
    assert "country" in df.columns
    assert "observation_date" in df.columns
    assert "location" in df.columns
    assert "series_key" in df.columns


def test_build_enriched_frame_derives_location(tmp_path):
    """build_enriched_frame should derive a canonical location column."""
    from cpi.fuel_prices.process import build_enriched_frame

    _write_malaysia_obs(
        tmp_path,
        [
            _fuel_row(subnational_area="National", city=None),
            _fuel_row(
                fuel_product="Diesel",
                fuel_family="diesel",
                quality_group="regular",
                city="Kuala Lumpur",
                subnational_area=None,
                observation_hash="kl-row",
            ),
        ],
    )

    df = build_enriched_frame(collect_dir=tmp_path)

    locations = set(df["location"].dropna())
    assert "National" in locations or "Kuala Lumpur" in locations


def test_build_enriched_frame_drops_philippines_ron97(tmp_path):
    """Philippines RON 97 should be dropped by data quality rules."""
    from cpi.fuel_prices.process import build_enriched_frame

    ph_csv = tmp_path / "philippines" / "ph_doe_retail_pump_prices" / "observations.csv"
    ph_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                country="Philippines",
                wb_iso3="PHL",
                fuel_product="RON 97",
                source_key="ph_doe_retail_pump_prices",
                observation_hash="ph-ron97",
            )
        ]
    ).to_csv(ph_csv, index=False)

    _write_malaysia_obs(tmp_path, [_fuel_row(observation_hash="my-row")])

    df = build_enriched_frame(collect_dir=tmp_path)

    assert "Philippines" not in set(df["country"])


def test_materialize_outputs_writes_enriched_csv(tmp_path):
    """materialize_outputs should write retail_series_enriched.csv."""
    from cpi.fuel_prices.process import materialize_outputs

    _write_malaysia_obs(tmp_path, [_fuel_row()])

    result = materialize_outputs(
        staged_dir=tmp_path / "staged",
        collect_dir=tmp_path,
    )

    assert result["enriched_path"].exists()
    assert result["enriched_rows"] > 0


def test_frame_to_country_series_groups_by_country():
    """frame_to_country_series should group rows by country."""
    from cpi.fuel_prices.process import frame_to_country_series

    df = pd.DataFrame(
        [
            {
                "country": "Malaysia",
                "observation_date": pd.Timestamp("2026-01-01"),
                "price_local": 2.05,
            },
            {
                "country": "Singapore",
                "observation_date": pd.Timestamp("2026-01-01"),
                "price_local": 2.85,
            },
        ]
    )

    series = frame_to_country_series(df)
    assert "Malaysia" in series
    assert "Singapore" in series
    assert len(series["Malaysia"]) == 1
    assert series["Malaysia"][0]["price_local"] == 2.05


def test_build_enriched_frame_refreshes_stale_state_controlled_cache(
    tmp_path, monkeypatch
):
    from cpi.fuel_prices import process

    staged_dir = tmp_path / "staged"
    monkeypatch.setattr(process, "STAGED_DATA_DIR", staged_dir)

    _write_malaysia_obs(tmp_path, [_fuel_row(observation_date="2026-01-01")])

    monkeypatch.setattr(process, "_today", lambda: date(2026, 1, 1))
    initial = process.build_enriched_frame(collect_dir=tmp_path, incremental=False)

    enriched_path = staged_dir / "enrich" / "retail_series_enriched.csv"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    initial.to_csv(enriched_path, index=False)

    newer = enriched_path.stat().st_mtime + 10
    os.utime(enriched_path, (newer, newer))
    older = newer - 20
    source_path = tmp_path / "malaysia" / "my_mof_weekly_petroleum" / "observations.csv"
    os.utime(source_path, (older, older))

    monkeypatch.setattr(process, "_today", lambda: date(2026, 1, 3))
    refreshed = process.build_enriched_frame(collect_dir=tmp_path, incremental=True)

    malaysia = refreshed[refreshed["country"] == "Malaysia"].sort_values(
        "observation_date"
    )
    assert malaysia["observation_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
    ]
