import pandas as pd
import pytest

from prices.enrich import shards

pytestmark = pytest.mark.unit


def raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "url_hash": ["a", "b", "c"],
            "product_name": ["Leite 1L", "Arroz 5kg", "Ovos"],
            # The three shapes that defeat per-file inference: EU decimal comma,
            # a thousands-dot that reads as a float, and a missing price.
            "price": ["R$ 1.234,56", "1.234", None],
            "currency": ["BRL", "BRL", "BRL"],
            "country": ["brazil"] * 3,
            "source": ["carrefour"] * 3,
            "date": ["2026-01-02T10:00:00Z", "20251212100333", ""],
            "product_url": ["https://x/1", "https://x/2", ""],
            "product_id": ["1", "2", None],
            "region": ["lac"] * 3,
            "subregion": ["south_america"] * 3,
            "wayback": [False, True, False],
            "channel": ["retail"] * 3,
            "category": ["dairy", "grains", ""],
            "details": ["", "5 kg", ""],
        }
    )


def test_round_trip_preserves_the_raw_price_text(tmp_path):
    df = raw_frame()
    path = shards.write_shard(df, tmp_path / "carrefour.parquet")
    back = shards.read_shard(path)
    assert list(back["price"]) == ["R$ 1.234,56", "1.234", None]


def test_price_stays_text_even_when_every_value_looks_numeric(tmp_path):
    """The x100 corruption shape: a shard whose prices all parse as floats.
    Inference would make this column float64 and 1.234 would mean one point
    two three four, not one thousand two hundred thirty four."""
    df = raw_frame()
    df["price"] = ["1.234", "12.50", "9"]
    path = shards.write_shard(df, tmp_path / "s.parquet")
    back = shards.read_shard(path)
    assert list(back["price"]) == ["1.234", "12.50", "9"]
    assert back["price"].dtype == object


def test_schema_is_string_for_price_and_date(tmp_path):
    import pyarrow.parquet as pq

    path = shards.write_shard(raw_frame(), tmp_path / "s.parquet")
    schema = pq.read_schema(path)
    assert schema.field("price").type == "string"
    assert schema.field("date").type == "string"
    assert schema.field("wayback").type == "bool"


def test_missing_price_is_null_not_the_string_nan(tmp_path):
    df = raw_frame()
    df["price"] = [float("nan"), 12.5, None]
    path = shards.write_shard(df, tmp_path / "s.parquet")
    back = shards.read_shard(path)
    assert back["price"].isna().tolist() == [True, False, True]
    assert back["price"].iloc[1] == "12.5"


def test_column_order_and_set_are_fixed(tmp_path):
    df = raw_frame().drop(columns=["details"])
    df["unexpected"] = 1
    path = shards.write_shard(df, tmp_path / "s.parquet")
    back = shards.read_shard(path)
    assert list(back.columns) == list(shards.SHARD_COLUMNS)
    assert back["details"].isna().all()


def test_wayback_survives_as_bool(tmp_path):
    path = shards.write_shard(raw_frame(), tmp_path / "s.parquet")
    back = shards.read_shard(path)
    assert list(back["wayback"]) == [False, True, False]


def test_csv_shard_reads_identically_to_parquet(tmp_path):
    df = raw_frame()
    csv_path = tmp_path / "s.csv"
    shards.coerce(df).to_csv(csv_path, index=False)
    parquet_path = shards.write_shard(df, tmp_path / "s.parquet")

    from_csv = shards.read_shard(csv_path)
    from_parquet = shards.read_shard(parquet_path)
    assert list(from_csv["price"]) == list(from_parquet["price"])
    assert list(from_csv["wayback"]) == list(from_parquet["wayback"])
    assert list(from_csv.columns) == list(from_parquet.columns)


def test_column_subset_is_pushed_down(tmp_path):
    path = shards.write_shard(raw_frame(), tmp_path / "s.parquet")
    back = shards.read_shard(path, columns=["product_name", "price"])
    assert list(back.columns) == ["product_name", "price"]


def test_read_shards_concatenates(tmp_path):
    a = shards.write_shard(raw_frame(), tmp_path / "a.parquet")
    b = shards.write_shard(raw_frame(), tmp_path / "b.parquet")
    out = shards.read_shards([a, b])
    assert len(out) == 6
    assert list(out.columns) == list(shards.SHARD_COLUMNS)


def test_read_shards_of_nothing_has_the_schema_columns():
    out = shards.read_shards([])
    assert list(out.columns) == list(shards.SHARD_COLUMNS)
    assert out.empty
