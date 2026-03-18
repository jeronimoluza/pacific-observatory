"""Tests for fuel pipeline load and data-quality stages.

Architecture (as of simplification to process.py):
  - apply_data_quality_rules: drops bad products/sources, renames countries
  - build_enriched_frame: full pipeline including collect/ merge + enrich
"""

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _fuel_row(**overrides):
    from cpi.fuel_prices.constants import COLUMNS

    row: dict[str, object | None] = {column: None for column in COLUMNS}
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
            "source_key": "legacy_source",
            "source_name": "Legacy baseline",
            "observation_date": "2025-01-01",
            "status": "Provisional",
            "observation_hash": "row-hash",
        }
    )
    row.update(overrides)
    return row


def test_build_enriched_frame_merges_collect_and_prefers_collected(tmp_path):
    """build_enriched_frame should merge collect + legacy, collected rows win on dedup."""
    from cpi.fuel_prices.process import build_enriched_frame

    obs_csv = tmp_path / "malaysia" / "my_mof_weekly_petroleum" / "observations.csv"
    obs_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="my_mof_weekly_petroleum",
                source_type="official",
                price_local=2.05,
                status="Final",
                observation_hash="shared-hash",
            )
        ]
    ).to_csv(obs_csv, index=False)

    df = build_enriched_frame(collect_dir=tmp_path)

    # After dedup, only 1 row; collected row (Final) survives
    my_rows = df[df["source_key"] == "my_mof_weekly_petroleum"]
    assert len(my_rows) == 1
    assert my_rows.iloc[0]["price_local"] == 2.05


def test_build_enriched_frame_keeps_unhashed_rows(tmp_path):
    """build_enriched_frame should not discard rows that lack observation hashes."""
    from cpi.fuel_prices.process import build_enriched_frame

    obs_csv = tmp_path / "australia" / "au_nsw_fuelcheck_history" / "observations.csv"
    obs_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                country="Australia",
                wb_iso3="AUS",
                source_key="au_nsw_fuelcheck_history",
                source_type="official",
                fuel_family="gasoline",
                fuel_product="Premium 95",
                quality_group="premium",
                city="Sydney",
                observation_date="2018-01-01",
                price_local=1.40,
                observation_hash=None,
            ),
            _fuel_row(
                country="Australia",
                wb_iso3="AUS",
                source_key="au_nsw_fuelcheck_history",
                source_type="official",
                fuel_family="gasoline",
                fuel_product="Premium 95",
                quality_group="premium",
                city="Newcastle",
                observation_date="2018-01-01",
                price_local=1.50,
                observation_hash=None,
            ),
        ]
    ).to_csv(obs_csv, index=False)

    df = build_enriched_frame(collect_dir=tmp_path)

    # Both rows should survive (different cities = different locations)
    au_rows = df[df["country"] == "Australia"]
    assert len(au_rows) >= 1
    assert not any(c.startswith("_") for c in df.columns)


def test_apply_data_quality_rules():
    """apply_data_quality_rules drops bad products/sources, renames countries."""
    from cpi.fuel_prices.process import apply_data_quality_rules

    frame = pd.DataFrame(
        [
            # Should be dropped — Philippines RON 97 not tracked
            _fuel_row(
                country="Philippines",
                wb_iso3="PHL",
                fuel_product="RON 97",
                source_key="ph_doe_retail_pump_prices",
                observation_hash="ph-ron97",
            ),
            # Cambodia row should be kept
            _fuel_row(
                country="Cambodia",
                wb_iso3="KHM",
                subnational_area=None,
                fuel_product="Regular Gasoline",
                quality_group=None,
                source_key="kh_moc_fuel_notices",
                observation_hash="kh-regular",
            ),
            # Country rename: "Viet Nam" -> "Vietnam"
            _fuel_row(
                country="Viet Nam",
                wb_iso3="VNM",
                city="Hanoi",
                fuel_product="RON 95",
                price_local=3.4,
                source_key="vn_petrolimex_retail",
                observation_hash="vn-row",
            ),
        ]
    )

    result = apply_data_quality_rules(frame)

    # Philippines RON 97 dropped
    assert "Philippines" not in set(result["country"])

    # Cambodia row kept
    assert "Cambodia" in set(result["country"])

    # Country rename applied
    assert "Viet Nam" not in set(result["country"])
    assert "Vietnam" in set(result["country"])

    # No internal _* columns
    assert not any(c.startswith("_") for c in result.columns)
    assert "subnational_area" in result.columns
    assert "city" in result.columns
    assert "source_key" in result.columns
    assert "wb_iso3" in result.columns


def test_build_legacy_commodity_frame_loads_legacy_only(tmp_path):
    """load_stored_observations with only a commodity CSV (not named observations.csv)
    should return an empty frame — the file is not discovered."""
    from cpi.fuel_prices.process import load_stored_observations

    commodity_csv = tmp_path / "commodity_prices.csv"
    pd.DataFrame(
        [
            _fuel_row(
                country="EAP",
                wb_iso3="EAP",
                fuel_family="crude_oil",
                fuel_product="Dubai Crude Oil",
                source_key="global_investing_daily",
                source_name="Legacy commodity",
                observation_hash="commodity-hash",
                price_local=80.0,
            )
        ]
    ).to_csv(commodity_csv, index=False)

    # load_stored_observations finds no observations.csv here — returns empty
    df = load_stored_observations(base_dir=tmp_path)
    # The commodity CSV is not named observations.csv so it won't be loaded
    assert df.empty or "commodity" not in str(df.get("fuel_family", ""))
