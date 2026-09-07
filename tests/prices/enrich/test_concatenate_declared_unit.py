"""The fetcher-declared `unit` column must survive ingestion.

`declared_unit.py` exists to turn a fetcher's sale-unit string ("quintal
(100 kg)", "kg") into structural quantity fields, and `classify._structural_fields`
consults it whenever the name and `details` found no quantity. `prepare` carries
a `unit` column and `products_input.parquet` has the field. But `concatenate`
-- the stage that maps a `price_observations.csv` row into the corpus schema --
never emitted it, so the column arrived empty and both were dead code: 0
non-empty `unit` values in a 5.46M-row scan of products_input.

Measured on the raw fetcher artifacts: 4,917,116 of 5,350,817 observation rows
in classifier-marked sources carry a non-empty `unit`, and 3,509,830 of those
parse to a mass/volume declaration -- malaysia 1.69M, china 0.74M, india 0.52M,
israel 0.25M, and 60+ more countries. For a commodity feed the declared unit is
the ONLY quantity in the row: 100% of agmarknet's and moa_wholesale's distinct
item names, and 82% of xinfadi's, are bare nouns ("Ajwan", "丝瓜") that the
structural regex correctly reads as `item`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prices.enrich.stages import concatenate

pytestmark = pytest.mark.unit


def _write_price_obs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "item_name": "Ajwan",
                "price_local": "9100",
                "currency": "INR",
                "observation_date": "2026-01-02",
                "source_url": "https://agmarknet/x",
                "observation_hash": "h1",
                "unit": "quintal (100 kg)",
            },
            {
                "item_name": "丝瓜",
                "price_local": "6.5",
                "currency": "CNY",
                "observation_date": "2026-01-02",
                "source_url": "https://xinfadi/y",
                "observation_hash": "h2",
                "unit": "kg",
            },
        ]
    ).to_csv(path, index=False)


def test_price_observations_unit_is_emitted(tmp_path):
    csv = tmp_path / "price_observations.csv"
    _write_price_obs(csv)
    rows = list(concatenate._emit_price_obs(csv))
    assert [r["unit"] for r in rows] == ["quintal (100 kg)", "kg"]


def test_unit_is_in_the_output_schema():
    assert "unit" in concatenate.OUTPUT_COLS


def test_unit_survives_the_column_projection(tmp_path, monkeypatch):
    monkeypatch.setattr(concatenate, "_channel_for", lambda country, source: "retail")
    monkeypatch.setattr(
        concatenate, "_classifier_csv_map", lambda: {("india", "agmarknet"): ""}
    )
    source_dir = tmp_path / "sar" / "south_asia" / "india" / "agmarknet"
    _write_price_obs(source_dir / "price_observations.csv")

    df = concatenate._load_source(
        source_dir, "sar", "south_asia", "india", "agmarknet"
    )
    assert df is not None
    assert list(df["unit"]) == ["quintal (100 kg)", "kg"]


def test_a_source_with_no_unit_column_still_loads(tmp_path, monkeypatch):
    """Spider JSONL carries no `unit`; the projection must backfill it to ""
    rather than fail, exactly as it does for `details`."""
    import json

    monkeypatch.setattr(concatenate, "_channel_for", lambda country, source: "retail")
    monkeypatch.setattr(concatenate, "_classifier_csv_map", dict)
    source_dir = tmp_path / "eap" / "pacific" / "fiji" / "shop_a"
    raw = source_dir / "raw_items"
    raw.mkdir(parents=True)
    (raw / "a.jsonl").write_text(
        json.dumps(
            {
                "product_name": "Rice 1kg",
                "price": "1.23",
                "currency": "FJD",
                "scraped_at_utc": "2026-01-02T10:00:00Z",
                "url": "https://a/rice",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    df = concatenate._load_source(source_dir, "eap", "pacific", "fiji", "shop_a")
    assert df is not None
    assert list(df["unit"]) == [""]
