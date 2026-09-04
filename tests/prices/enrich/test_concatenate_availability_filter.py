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


def _row(product_id, price, **extra):
    row = {
        "product_name": f"Item {product_id}",
        "price": price,
        "currency": "ARS",
        "scraped_at_utc": "2026-09-02T14:36:42Z",
        "url": f"https://d/{product_id}",
        "product_id": product_id,
        "category": "",
        "details": "",
    }
    row.update(extra)
    return row


@pytest.fixture
def env(tmp_path, monkeypatch):
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
    return {"data_root": data_root, "out_dir": out_dir, "per_source": per_source}


def _disco(env, records):
    write_jsonl(
        env["data_root"]
        / "lac"
        / "south_america"
        / "argentina"
        / "disco_ar"
        / "raw_items"
        / "a.jsonl",
        records,
    )


def _shard(env):
    return shards.read_shard(
        env["per_source"] / "lac/south_america/argentina/disco_ar.parquet"
    )


def test_rows_without_an_available_key_are_all_kept(env):
    """THE catastrophic case. Most spiders never emit `available`; treating a
    missing key as unavailable would silently delete most of the corpus."""
    _disco(env, [_row("a", "100"), _row("b", "200"), _row("c", "300")])
    concatenate.run()
    assert sorted(_shard(env)["product_id"]) == ["a", "b", "c"]


def test_null_available_is_kept(env):
    _disco(env, [_row("a", "100", available=None)])
    concatenate.run()
    assert list(_shard(env)["product_id"]) == ["a"]


def test_non_boolean_available_is_kept(env):
    """Only a real JSON `false` means out of stock. 0, "" and "false" are
    shapes no spider emits; keeping them is the safe direction."""
    _disco(
        env,
        [
            _row("a", "100", available=0),
            _row("b", "200", available=""),
            _row("c", "300", available="false"),
        ],
    )
    concatenate.run()
    assert sorted(_shard(env)["product_id"]) == ["a", "b", "c"]


def test_available_false_is_dropped(env):
    """The disco/jumbo/vea defect: out-of-stock SKUs carry a price frozen
    years ago (35.55 ARS for icing sugar) and must not enter the corpus."""
    _disco(
        env,
        [
            _row("stale", "35.55", available=False),
            _row("live", "2350.0", available=True),
        ],
    )
    concatenate.run()
    assert list(_shard(env)["product_id"]) == ["live"]


def test_drop_count_is_logged_per_source_and_in_total(env, caplog):
    _disco(
        env,
        [
            _row("stale1", "35.55", available=False),
            _row("stale2", "1.89", available=False),
            _row("live", "2350.0", available=True),
        ],
    )
    write_jsonl(
        env["data_root"]
        / "eap"
        / "pacific"
        / "fiji"
        / "shop_a"
        / "raw_items"
        / "a.jsonl",
        [_row("keep", "4.50", currency="FJD")],
    )
    with caplog.at_level("INFO"):
        concatenate.run()
    assert "argentina/disco_ar: dropped 2 out-of-stock rows" in caplog.text
    assert "dropped 2 out-of-stock rows across 1 source" in caplog.text


def test_a_source_that_is_entirely_out_of_stock_yields_no_shard(env):
    _disco(env, [_row("stale", "35.55", available=False)])
    write_jsonl(
        env["data_root"]
        / "eap"
        / "pacific"
        / "fiji"
        / "shop_a"
        / "raw_items"
        / "a.jsonl",
        [_row("keep", "4.50", currency="FJD")],
    )
    concatenate.run()
    assert not (
        env["per_source"] / "lac/south_america/argentina/disco_ar.parquet"
    ).exists()
    monolith = pd.read_csv(env["out_dir"] / "raw_prices.csv", dtype=str)
    assert list(monolith["product_id"]) == ["keep"]


def test_common_crawl_rows_are_filtered_too(env):
    cc_dir = (
        env["data_root"]
        / "lac"
        / "south_america"
        / "argentina"
        / "disco_ar"
        / "common_crawl_data"
        / "items"
    )
    cc_dir.mkdir(parents=True, exist_ok=True)
    (cc_dir / "stale.json").write_text(
        json.dumps(
            {
                "product_name": "Azucar",
                "price": "35.55",
                "currency": "ARS",
                "cc_timestamp": "2021-10-01T00:00:00Z",
                "url": "https://d/azucar",
                "product_id": "stale",
                "available": False,
            }
        )
    )
    (cc_dir / "live.json").write_text(
        json.dumps(
            {
                "product_name": "Arroz",
                "price": "2350.0",
                "currency": "ARS",
                "cc_timestamp": "2021-10-01T00:00:00Z",
                "url": "https://d/arroz",
                "product_id": "live",
            }
        )
    )
    concatenate.run()
    assert list(_shard(env)["product_id"]) == ["live"]
