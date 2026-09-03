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


def reference_hashes(df: pd.DataFrame) -> list[str]:
    """input_hash exactly as prepare computes it, row by row."""
    from prices.enrich.stages.prepare import _row_input_dict
    from prices.enrich.versioning import input_hash

    return [input_hash(_row_input_dict(row)) for _, row in df.iterrows()]


def test_stored_input_hash_matches_prepare_row_for_row(tmp_path):
    """If these ever diverge, observations stop joining to the classifier and
    the dashboard loses rows silently."""
    df = raw_frame()
    # Row 3 has no URL, so it takes the (name, country, currency) fallback.
    path = shards.write_shard(df, tmp_path / "s.parquet")
    back = shards.read_shard(path)
    assert list(back["input_hash"]) == reference_hashes(df)


def test_url_and_urlless_rows_take_different_identity_branches(tmp_path):
    df = raw_frame()
    df["product_url"] = ["https://x/1", "", None]
    df["product_name"] = ["Same", "Same", "Same"]
    path = shards.write_shard(df, tmp_path / "s.parquet")
    hashes = list(shards.read_shard(path)["input_hash"])
    assert hashes == reference_hashes(df)
    # The two URL-less rows share an identity; the URL row does not join them.
    assert hashes[1] == hashes[2] != hashes[0]


def test_input_hash_is_derived_when_absent_from_the_frame(tmp_path):
    df = raw_frame()
    assert "input_hash" not in df.columns
    back = shards.read_shard(shards.write_shard(df, tmp_path / "s.parquet"))
    assert back["input_hash"].notna().all()


def test_a_supplied_input_hash_is_kept(tmp_path):
    df = raw_frame()
    df["input_hash"] = ["a", "b", "c"]
    back = shards.read_shard(shards.write_shard(df, tmp_path / "s.parquet"))
    assert list(back["input_hash"]) == ["a", "b", "c"]


def test_legacy_csv_shard_gains_an_input_hash_on_conversion(tmp_path):
    """The 1,164 CSV shards on disk have no hash column; converting must add it
    rather than write a column of nulls."""
    df = raw_frame()
    csv_path = tmp_path / "s.csv"
    df.to_csv(csv_path, index=False)
    from_csv = shards.read_shard(csv_path)
    assert from_csv["input_hash"].isna().all()
    converted = shards.read_shard(shards.write_shard(from_csv, tmp_path / "s.parquet"))
    assert list(converted["input_hash"]) == reference_hashes(df)


def test_read_shards_of_nothing_has_the_schema_columns():
    out = shards.read_shards([])
    assert list(out.columns) == list(shards.SHARD_COLUMNS)
    assert out.empty
