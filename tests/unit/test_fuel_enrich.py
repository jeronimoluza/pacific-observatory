"""Tests for enrich-stage canonicalization and dashboard-series preparation."""

from datetime import date
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _fuel_row(**overrides):
    from cpi.fuel_prices.constants import COLUMNS

    row: dict[str, object | None] = {column: None for column in COLUMNS}
    row.update(
        {
            "country": "Australia",
            "wb_iso3": "AUS",
            "subnational_area": "National",
            "city": None,
            "fuel_family": "gasoline",
            "fuel_product": "Unleaded",
            "quality_group": "regular",
            "price_local": 1.75,
            "currency": "AUD",
            "unit": "L",
            "source_key": "test_source",
            "source_name": "Test source",
            "source_type": "official",
            "observation_date": "2026-03-12",
            "status": "Final",
            "consumer_segment": "retail",
            "observation_hash": "row-hash",
        }
    )
    row.update(overrides)
    return row


def test_build_enriched_frame_prefers_better_australia_sources(tmp_path):
    from cpi.fuel_prices.process import build_enriched_frame

    aip_csv = tmp_path / "australia" / "au_aip_tgp_weekly" / "observations.csv"
    aip_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="au_aip_tgp_weekly",
                source_name="AIP",
                source_type="industry",
                consumer_segment="wholesale",
                fuel_family="diesel",
                fuel_product="Diesel",
                quality_group="regular",
                city="Perth",
                subnational_area="Perth",
                price_local=1.65,
                observation_hash="aip-diesel",
            )
        ]
    ).to_csv(aip_csv, index=False)

    fuelwatch_csv = (
        tmp_path / "australia" / "au_fuelwatch_perth_daily" / "observations.csv"
    )
    fuelwatch_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="au_fuelwatch_perth_daily",
                source_name="FuelWatch",
                source_type="official",
                consumer_segment="retail",
                fuel_family="diesel",
                fuel_product="Diesel",
                quality_group="regular",
                city="Perth",
                subnational_area="South of River",
                price_local=1.80,
                observation_hash="fuelwatch-diesel",
            )
        ]
    ).to_csv(fuelwatch_csv, index=False)

    gpp_csv = tmp_path / "australia" / "gpp_AUS_gasoline_weekly" / "observations.csv"
    gpp_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="gpp_AUS_gasoline_weekly",
                source_name="GPP",
                source_type="aggregator",
                fuel_family="gasoline",
                fuel_product="Gasoline (Octane-95)",
                quality_group="premium",
                subnational_area="National",
                city=None,
                price_local=1.95,
                observation_date="2026-03-08",
                observation_hash="gpp-p95",
            )
        ]
    ).to_csv(gpp_csv, index=False)

    accc_csv = (
        tmp_path / "australia" / "au_accc_5largestcities_quarterly" / "observations.csv"
    )
    accc_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="au_accc_5largestcities_quarterly",
                source_name="ACCC",
                source_type="official",
                fuel_family="gasoline",
                fuel_product="ULP 91 average",
                quality_group="regular",
                city="5 largest cities average",
                subnational_area="National",
                price_local=1.70,
                observation_date="2025-03-31",
                observation_hash="accc-ulp",
            )
        ]
    ).to_csv(accc_csv, index=False)

    enriched = build_enriched_frame(collect_dir=tmp_path, incremental=False)

    perth = enriched[
        (enriched["observation_date"] == pd.Timestamp("2026-03-12"))
        & (enriched["location"] == "Perth")
        & (enriched["series_key"] == "diesel|||regular")
    ]
    assert len(perth) == 1
    assert perth.iloc[0]["source_key"] == "au_fuelwatch_perth_daily"
    assert perth.iloc[0]["series_label"] == "Diesel - Regular"

    by_source = dict(zip(enriched["source_key"], enriched["series_label"]))
    assert by_source["gpp_AUS_gasoline_weekly"] == "Gasoline - Premium"
    assert by_source["au_accc_5largestcities_quarterly"] == "Gasoline - Regular"


def test_build_enriched_frame_averages_same_location_duplicates(tmp_path):
    from cpi.fuel_prices.process import build_enriched_frame

    nsw_csv = tmp_path / "australia" / "au_nsw_fuelcheck_history" / "observations.csv"
    nsw_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                source_key="au_nsw_fuelcheck_history",
                source_name="NSW FuelCheck",
                source_type="official",
                fuel_family="gasoline",
                fuel_product="Unleaded 91",
                quality_group="regular",
                subnational_area="New South Wales",
                city="INGLEBURN",
                price_local=1.80,
                observation_date="2026-02-24",
                observation_hash="nsw-1",
            ),
            _fuel_row(
                source_key="au_nsw_fuelcheck_history",
                source_name="NSW FuelCheck",
                source_type="official",
                fuel_family="gasoline",
                fuel_product="Unleaded 91",
                quality_group="regular",
                subnational_area="New South Wales",
                city="Ingleburn",
                price_local=1.90,
                observation_date="2026-02-24",
                observation_hash="nsw-2",
            ),
        ]
    ).to_csv(nsw_csv, index=False)

    enriched = build_enriched_frame(collect_dir=tmp_path)

    assert len(enriched) == 1
    row = enriched.iloc[0]
    assert row["location"] == "Ingleburn"
    assert row["series_key"] == "gasoline|||regular"
    assert row["series_label"] == "Gasoline - Regular"
    assert row["price_local"] == 1.85


def test_build_enriched_frame_forward_fills_state_controlled_series(
    tmp_path, monkeypatch
):
    from cpi.fuel_prices import process

    monkeypatch.setattr(process, "_today", lambda: date(2026, 3, 5))

    kh_csv = tmp_path / "cambodia" / "kh_ptt_monthly_prices" / "observations.csv"
    kh_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                country="Cambodia",
                wb_iso3="KHM",
                source_key="kh_ptt_monthly_prices",
                source_name="PTT Cambodia",
                fuel_product="Regular",
                fuel_family="gasoline",
                quality_group="regular",
                currency="KHR",
                price_local=4200,
                observation_date="2026-03-01",
                observation_hash="kh-1",
            ),
            _fuel_row(
                country="Cambodia",
                wb_iso3="KHM",
                source_key="kh_ptt_monthly_prices",
                source_name="PTT Cambodia",
                fuel_product="Regular",
                fuel_family="gasoline",
                quality_group="regular",
                currency="KHR",
                price_local=4300,
                observation_date="2026-03-03",
                observation_hash="kh-2",
            ),
        ]
    ).to_csv(kh_csv, index=False)

    enriched = process.build_enriched_frame(collect_dir=tmp_path, incremental=False)
    filled = enriched[
        (enriched["country"] == "Cambodia")
        & (enriched["fuel_product"] == "Regular")
        & (enriched["location"] == "National")
    ].sort_values("observation_date")

    assert filled["observation_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-03-01",
        "2026-03-02",
        "2026-03-03",
        "2026-03-04",
        "2026-03-05",
    ]
    assert filled["price_local"].tolist() == [4200.0, 4200.0, 4300.0, 4300.0, 4300.0]
    assert filled["observation_hash"].nunique() == len(filled)


def test_build_enriched_frame_forward_fill_preserves_series_boundaries(
    tmp_path, monkeypatch
):
    from cpi.fuel_prices import process

    monkeypatch.setattr(process, "_today", lambda: date(2026, 1, 3))

    my_csv = tmp_path / "cambodia" / "kh_ptt_monthly_prices" / "observations.csv"
    my_csv.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            _fuel_row(
                country="Cambodia",
                wb_iso3="KHM",
                source_key="kh_ptt_monthly_prices",
                source_name="PTT Cambodia",
                fuel_product="Regular",
                fuel_family="gasoline",
                quality_group="regular",
                currency="KHR",
                subnational_area="Phnom Penh",
                price_local=4200,
                observation_date="2026-01-01",
                observation_hash="kh-pp-1",
            ),
            _fuel_row(
                country="Cambodia",
                wb_iso3="KHM",
                source_key="kh_ptt_monthly_prices",
                source_name="PTT Cambodia",
                fuel_product="Regular",
                fuel_family="gasoline",
                quality_group="regular",
                currency="KHR",
                subnational_area="Siem Reap",
                price_local=4300,
                observation_date="2026-01-02",
                observation_hash="kh-sr-1",
            ),
        ]
    ).to_csv(my_csv, index=False)

    enriched = process.build_enriched_frame(collect_dir=tmp_path, incremental=False)

    phnom_penh = enriched[
        (enriched["country"] == "Cambodia") & (enriched["location"] == "Phnom Penh")
    ].sort_values("observation_date")
    siem_reap = enriched[
        (enriched["country"] == "Cambodia") & (enriched["location"] == "Siem Reap")
    ].sort_values("observation_date")

    assert phnom_penh["observation_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
    ]
    assert phnom_penh["price_local"].tolist() == [4200.0, 4200.0, 4200.0]

    assert siem_reap["observation_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-02",
        "2026-01-03",
    ]
    assert siem_reap["price_local"].tolist() == [4300.0, 4300.0]
