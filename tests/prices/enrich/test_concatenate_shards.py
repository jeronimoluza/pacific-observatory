import json
from pathlib import Path

import pandas as pd
import pytest

from prices.enrich import shards
from prices.enrich.stages import concatenate

pytestmark = pytest.mark.unit


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A miniature data/prices tree plus isolated concatenate outputs."""
    data_root = tmp_path / "data" / "prices"
    out_dir = tmp_path / "outputs" / "prices" / "raw"
    per_source = out_dir / "_per_source"

    monkeypatch.setattr(concatenate, "DATA_PRICES_ROOT", data_root)
    monkeypatch.setattr(concatenate, "RAW_OUT_DIR", out_dir)
    monkeypatch.setattr(concatenate, "PER_SOURCE_DIR", per_source)
    monkeypatch.setattr(concatenate, "RAW_CSV", out_dir / "raw_prices.csv")
    monkeypatch.setattr(concatenate, "STATE_FILE", out_dir / ".state.json")
    monkeypatch.setattr(concatenate, "_channel_for", lambda country, source: "retail")
    monkeypatch.setattr(concatenate, "_classifier_csv_map", dict)

    write_jsonl(
        data_root / "eap" / "pacific" / "fiji" / "shop_a" / "raw_items" / "a.jsonl",
        [
            {
                "product_name": "Rice 1kg",
                # A price whose text would infer as a float and lose its meaning.
                "price": "1.234",
                "currency": "FJD",
                "scraped_at_utc": "2026-01-02T10:00:00Z",
                "url": "https://a/rice",
                "product_id": "r1",
                "category": "grains",
                "details": "",
            },
            {
                "product_name": "Milk 1L",
                "price": "4.50",
                "currency": "FJD",
                "scraped_at_utc": "2026-01-02T10:00:00Z",
                "url": "https://a/milk",
                "product_id": "m1",
                "category": "dairy",
                "details": "1 L",
            },
        ],
    )
    write_jsonl(
        data_root / "ssa" / "western" / "ghana" / "esoko" / "raw_items" / "a.jsonl",
        [
            {
                "product_name": "Yam 1kg",
                "price": "5",
                "currency": "GHS",
                "scraped_at_utc": "2026-01-02T10:00:00Z",
                "url": "https://e/yam",
                "product_id": "y1",
                "category": "",
                "details": "",
            }
        ],
    )
    return {"data_root": data_root, "out_dir": out_dir, "per_source": per_source}


def test_shards_are_parquet_at_the_partition_path(env):
    concatenate.run()
    assert sorted(
        p.relative_to(env["per_source"]).as_posix()
        for p in env["per_source"].rglob("*.parquet")
    ) == [
        "eap/pacific/fiji/shop_a.parquet",
        "ssa/western/ghana/esoko.parquet",
    ]
    assert list(env["per_source"].rglob("*.csv")) == []


def test_shard_keeps_the_raw_price_text(env):
    concatenate.run()
    frame = shards.read_shard(env["per_source"] / "eap/pacific/fiji/shop_a.parquet")
    assert set(frame["price"]) == {"1.234", "4.50"}
    assert frame["price"].dtype == object


def test_monolith_is_still_written_and_holds_every_row(env):
    concatenate.run()
    monolith = pd.read_csv(env["out_dir"] / "raw_prices.csv", dtype=str)
    assert len(monolith) == 3
    assert list(monolith.columns) == list(shards.SHARD_COLUMNS)
    assert set(monolith["source"]) == {"shop_a", "esoko"}


def test_monolith_can_be_skipped(env):
    out = concatenate.run(write_monolith=False)
    assert out == env["per_source"]
    assert not (env["out_dir"] / "raw_prices.csv").exists()


def test_second_run_skips_unchanged_sources(env, caplog):
    concatenate.run()
    with caplog.at_level("INFO"):
        concatenate.run()
    assert "2 unchanged" in caplog.text


def test_a_legacy_csv_shard_is_converted_not_rederived(env, monkeypatch):
    """The format change alone must not re-derive every source from 43 GB of
    scrape output. An unchanged source whose shard is still CSV converts in
    place, and _load_source is never reached."""
    concatenate.run()
    for shard in list(env["per_source"].rglob("*.parquet")):
        shards.coerce(shards.read_shard(shard)).to_csv(
            shard.with_suffix(".csv"), index=False
        )
        shard.unlink()

    def explode(*args, **kwargs):
        raise AssertionError("_load_source was called for an unchanged source")

    monkeypatch.setattr(concatenate, "_load_source", explode)
    concatenate.run()

    converted = env["per_source"] / "eap/pacific/fiji/shop_a.parquet"
    assert converted.exists()
    assert set(shards.read_shard(converted)["price"]) == {"1.234", "4.50"}


def test_no_sources_at_all_raises(env, monkeypatch, tmp_path):
    empty = tmp_path / "empty"
    (empty / "eap" / "pacific" / "fiji" / "shop_a").mkdir(parents=True)
    monkeypatch.setattr(concatenate, "DATA_PRICES_ROOT", empty)
    with pytest.raises(RuntimeError):
        concatenate.run()
