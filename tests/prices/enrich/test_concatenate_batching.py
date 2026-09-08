"""A source is built in batches; the shard must not depend on the batch size.

`_load_source` used to hold a whole source as a list of dicts and hand it to
`pd.DataFrame` once, so pandas typed each column from every row at once.
Streaming the source through a spill types it one batch at a time instead, and
pandas types what it can see: a column of JSON integers is int64 in a batch with
no nulls and float64 in one with them, and float64 renders 13 as "13.0" where
int64 renders it as "13". Nothing in today's corpus emits a JSON number for
`price`, `product_id` or `date`, so nothing here would have failed loudly — it
would have changed a few sources' prices quietly if one ever did.

The invariant these tests pin is that the shard is a function of the source and
not of BATCH_ROWS.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pandas.testing import assert_frame_equal

from prices.enrich import shards
from prices.enrich.stages import concatenate

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_yaml_walk(monkeypatch):
    monkeypatch.setattr(concatenate, "_channel_for", lambda country, source: "retail")
    monkeypatch.setattr(concatenate, "_classifier_csv_map", dict)


def write_source(tmp_path: Path, records, name: str = "a.jsonl") -> Path:
    source_dir = tmp_path / "eap" / "pacific" / "fiji" / "shop_a"
    raw = source_dir / "raw_items"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / name).write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    return source_dir


def build(source_dir: Path, shard: Path, batch_rows: int, monkeypatch) -> int:
    monkeypatch.setattr(concatenate, "BATCH_ROWS", batch_rows)
    return concatenate._write_source_shard(
        source_dir, "eap", "pacific", "fiji", "shop_a", shard
    )


def item(name, **kw):
    record = {
        "product_name": name,
        "price": "9",
        "currency": "FJD",
        "scraped_at_utc": "2026-01-02T10:00:00Z",
        "url": f"https://a/{name}",
    }
    record.update(kw)
    return record


def test_the_batch_size_does_not_change_the_shard(tmp_path, monkeypatch):
    """The general invariant, over a source that mixes every shape the batch
    boundary can fall between: numeric and null prices, present, empty and
    missing currencies, numeric and null ids."""
    source_dir = write_source(
        tmp_path,
        [
            item("a", price=12, currency="AAA"),
            item("b", price=13, currency=""),
            item("c", price=12.5, currency="BBB"),
            item("d", price=None),
            item("e", price=14, currency=None, product_id=7),
            item("f", price=15, product_id=None),
        ],
    )
    whole = tmp_path / "whole.parquet"
    batched = tmp_path / "batched.parquet"
    assert build(source_dir, whole, 1_000_000, monkeypatch) == 5
    assert build(source_dir, batched, 2, monkeypatch) == 5
    assert_frame_equal(shards.read_shard(whole), shards.read_shard(batched))


def test_a_numeric_column_renders_as_the_whole_source_would(tmp_path, monkeypatch):
    """12 and 13 are int64 in their own batch and float64 over the source, and
    the shard has to say what the source says."""
    source_dir = write_source(
        tmp_path, [item("a", price=12), item("b", price=13), item("c", price=12.5)]
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 2, monkeypatch) == 3
    assert list(shards.read_shard(shard)["price"]) == ["12.0", "13.0", "12.5"]


def test_a_null_elsewhere_in_the_source_floats_the_whole_column(
    tmp_path, monkeypatch
):
    """A null price is dropped by the required-field screen, but it has already
    made the column float64 for the rows that survive."""
    source_dir = write_source(
        tmp_path, [item("a", price=12), item("b", price=13), item("c", price=None)]
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 2, monkeypatch) == 2
    assert list(shards.read_shard(shard)["price"]) == ["12.0", "13.0"]


def test_an_all_integer_column_with_no_nulls_keeps_its_integer_text(
    tmp_path, monkeypatch
):
    source_dir = write_source(
        tmp_path, [item("a", price=12), item("b", price=13), item("c", price=7)]
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 2, monkeypatch) == 3
    assert list(shards.read_shard(shard)["price"]) == ["12", "13", "7"]


def test_the_modal_currency_is_counted_over_the_whole_source(tmp_path, monkeypatch):
    """The back-fill is why the source cannot be written as it is read: the
    modal is only known after the last row."""
    source_dir = write_source(
        tmp_path,
        [
            item("a", currency="AAA"),
            item("b", currency=None),
            item("c", currency="BBB"),
            item("d", currency="BBB"),
        ],
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 2, monkeypatch) == 4
    assert list(shards.read_shard(shard)["currency"]) == ["AAA", "BBB", "BBB", "BBB"]


def test_a_modal_tie_breaks_on_first_appearance(tmp_path, monkeypatch):
    source_dir = write_source(
        tmp_path,
        [item("a", currency="AAA"), item("b", currency="BBB"), item("c", currency="")],
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 1, monkeypatch) == 3
    assert list(shards.read_shard(shard)["currency"]) == ["AAA", "BBB", "AAA"]


def test_a_source_with_no_currency_at_all_writes_no_shard(tmp_path, monkeypatch):
    """There is nothing to back-fill from, so every row fails the required-field
    screen and the source produces nothing — not an empty shard."""
    source_dir = write_source(
        tmp_path, [item("a", currency=None), item("b", currency=None)]
    )
    shard = tmp_path / "out.parquet"
    assert build(source_dir, shard, 1, monkeypatch) == 0
    assert not shard.exists()


def test_the_spill_is_cleaned_up(tmp_path, monkeypatch):
    source_dir = write_source(tmp_path, [item("a"), item("b")])
    shard = tmp_path / "out.parquet"
    build(source_dir, shard, 1, monkeypatch)
    assert shard.exists()
    assert not shard.with_suffix(concatenate.SPILL_SUFFIX).exists()
    assert list(tmp_path.glob("*" + concatenate.SPILL_SUFFIX)) == []
