"""Tests for observed fuel source inventory Excel export."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _write_enriched_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_build_source_key_metadata_prefers_fetcher_registry():
    from cpi.fuel_prices.source_inventory import build_source_key_metadata

    metadata = build_source_key_metadata(
        fetcher_registry={
            "test_source": SimpleNamespace(
                homepage="https://registry.example/source",
                cadence="daily",
                source_name="Registry Source",
                country="Testland",
            )
        },
        meta_entries=[
            {
                "source_keys": ["test_source"],
                "url": "https://meta.example/source",
                "source_name": "Meta Source",
                "country": "Meta Country",
            }
        ],
    )

    assert metadata["test_source"]["source_url"] == "https://registry.example/source"
    assert metadata["test_source"]["cadence"] == "daily"
    assert metadata["test_source"]["source_name"] == "Registry Source"


def test_build_source_inventory_rows_uses_observed_keys_and_raw_products(tmp_path):
    from cpi.fuel_prices.source_inventory import build_source_inventory_rows

    enriched_csv = _write_enriched_csv(
        tmp_path / "retail_series_enriched.csv",
        [
            {
                "observation_date": "2026-03-01",
                "fuel_product": "RON95",
                "source_key": "my_mof_weekly_petroleum",
            },
            {
                "observation_date": "2026-03-08",
                "fuel_product": "Diesel",
                "source_key": "my_mof_weekly_petroleum",
            },
            {
                "observation_date": "2026-03-15",
                "fuel_product": "RON95",
                "source_key": "my_mof_weekly_petroleum",
            },
            {
                "observation_date": "2026-03-02",
                "fuel_product": "Diesel (regular)",
                "source_key": "gpp_AUS_diesel_weekly",
            },
        ],
    )

    rows = build_source_inventory_rows(
        enriched_csv_path=enriched_csv,
        metadata_by_key={
            "my_mof_weekly_petroleum": {
                "source_url": "https://registry.example/mof",
                "cadence": "weekly",
            },
            "unobserved_source": {
                "source_url": "https://registry.example/unobserved",
                "cadence": "daily",
            },
        },
    )

    assert [row["source_key"] for row in rows] == [
        "gpp_AUS_diesel_weekly",
        "my_mof_weekly_petroleum",
    ]

    gpp_row = rows[0]
    assert gpp_row["n_observations"] == 1
    assert gpp_row["n_products"] == 1
    assert gpp_row["objective"] == "ancillary data"

    mof_row = rows[1]
    assert mof_row["source_url"] == "https://registry.example/mof"
    assert mof_row["cadence"] == "weekly"
    assert mof_row["n_observations"] == 3
    assert mof_row["n_products"] == 2
    assert mof_row["start_date"] == "2026-03-01"
    assert mof_row["end_date"] == "2026-03-15"
    assert mof_row["objective"] == "country fuel prices"


def test_classify_source_objective_uses_controlled_values():
    from cpi.fuel_prices.source_inventory import classify_source_objective

    assert (
        classify_source_objective("au_nsw_fuelcheck_history") == "country fuel prices"
    )
    assert classify_source_objective("global_investing_daily") == "commodity prices"
    assert classify_source_objective("gpp_AUS_gasoline_weekly") == "ancillary data"


def test_gen_sources_excel_writes_expected_workbook(tmp_path):
    from cpi.fuel_prices.gen_sources_excel import gen_sources_excel

    enriched_csv = _write_enriched_csv(
        tmp_path / "retail_series_enriched.csv",
        [
            {
                "observation_date": "2026-03-01",
                "fuel_product": "Unleaded",
                "source_key": "au_nsw_fuelcheck_history",
            },
            {
                "observation_date": "2026-03-02",
                "fuel_product": "Diesel",
                "source_key": "au_nsw_fuelcheck_history",
            },
        ],
    )
    out_path = tmp_path / "fuel_source_inventory.xlsx"

    generated = gen_sources_excel(out_path=out_path, enriched_csv_path=enriched_csv)

    assert generated == out_path
    assert out_path.exists()

    df = pd.read_excel(out_path)
    assert df.columns.tolist() == [
        "source_key",
        "source_url",
        "n_observations",
        "n_products",
        "start_date",
        "end_date",
        "cadence",
        "objective",
    ]
    assert df["source_key"].tolist() == ["au_nsw_fuelcheck_history"]
    assert int(df.loc[0, "n_observations"]) == 2
    assert int(df.loc[0, "n_products"]) == 2
    assert df.loc[0, "objective"] == "country fuel prices"
