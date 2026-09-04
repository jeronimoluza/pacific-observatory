import pandas as pd
import pyarrow as pa
import pytest

from prices.enrich.stages import decisions_store as ds

SCHEMA = pa.schema(
    [
        ("input_hash", pa.string()),
        ("country", pa.string()),
        ("coicop_code", pa.string()),
    ]
)


def _frame(rows):
    return pd.DataFrame(rows, columns=["input_hash", "country", "coicop_code"])


def test_parts_root_derives_dir_from_legacy_file(tmp_path):
    legacy = tmp_path / "decisions_hierlex.parquet"
    assert ds.parts_root(legacy) == tmp_path / "decisions_hierlex"
    # Already a directory: idempotent, so callers can pass either.
    assert (
        ds.parts_root(tmp_path / "decisions_hierlex") == tmp_path / "decisions_hierlex"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("fiji", "fiji"),
        ("taiwan_china", "taiwan_china"),
        ("cote d'ivoire", "cote_d_ivoire"),
        ("", ds.UNKNOWN_COUNTRY),
        (None, ds.UNKNOWN_COUNTRY),
        (float("nan"), ds.UNKNOWN_COUNTRY),
    ],
)
def test_part_name_is_filename_safe_and_never_drops_a_row(value, expected):
    assert ds.part_name(value) == expected


def test_write_splits_by_country_and_roundtrips(tmp_path):
    root = tmp_path / "decisions"
    frame = _frame(
        [
            ("h1", "fiji", "01.1.1"),
            ("h2", "samoa", "01.1.2"),
            ("h3", "fiji", "01.1.3"),
        ]
    )
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(frame)

    assert ds.existing_countries(root) == {"fiji", "samoa"}
    assert ds.row_count(root) == 3
    back = ds.read(root).sort_values("input_hash").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        back, frame.sort_values("input_hash").reset_index(drop=True)
    )


def test_rows_for_one_country_land_in_one_part_across_chunks(tmp_path):
    """A country's rows arrive spread over many chunks; they must not overwrite."""
    root = tmp_path / "decisions"
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(_frame([("h1", "fiji", "01.1.1")]))
        w.write(_frame([("h2", "samoa", "01.1.2")]))
        w.write(_frame([("h3", "fiji", "01.1.3")]))

    fiji = pd.read_parquet(root / "fiji.parquet")
    assert sorted(fiji["input_hash"]) == ["h1", "h3"]
    assert ds.row_count(root) == 3


def test_scoped_rewrite_leaves_other_countries_untouched(tmp_path):
    """The whole point: rewriting fiji must not disturb samoa's part."""
    root = tmp_path / "decisions"
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(_frame([("h1", "fiji", "01.1.1"), ("h2", "samoa", "01.1.2")]))
    samoa_before = (root / "samoa.parquet").read_bytes()

    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(_frame([("h9", "fiji", "02.2.2")]))

    assert (root / "samoa.parquet").read_bytes() == samoa_before
    assert sorted(pd.read_parquet(root / "fiji.parquet")["input_hash"]) == ["h9"]
    assert ds.row_count(root) == 2


def test_abort_leaves_previous_parts_intact(tmp_path):
    root = tmp_path / "decisions"
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(_frame([("h1", "fiji", "01.1.1")]))
    before = (root / "fiji.parquet").read_bytes()

    with pytest.raises(RuntimeError):
        with ds.PartitionedWriter(root, SCHEMA) as w:
            w.write(_frame([("h2", "fiji", "09.9.9")]))
            raise RuntimeError("killed mid-write")

    assert (root / "fiji.parquet").read_bytes() == before
    assert not list(root.glob("*.tmp"))


def test_read_prefers_the_directory_over_a_stale_legacy_file(tmp_path):
    """After a port the single file is stale; reading it would undo the port."""
    legacy = tmp_path / "decisions.parquet"
    _frame([("old", "fiji", "00.0.0")]).to_parquet(legacy, index=False)
    with ds.PartitionedWriter(ds.parts_root(legacy), SCHEMA) as w:
        w.write(_frame([("new", "fiji", "01.1.1")]))

    assert list(ds.read(legacy)["input_hash"]) == ["new"]


def test_read_falls_back_to_the_legacy_file_before_a_port(tmp_path):
    legacy = tmp_path / "decisions.parquet"
    _frame([("old", "fiji", "00.0.0")]).to_parquet(legacy, index=False)
    assert list(ds.read(legacy)["input_hash"]) == ["old"]
    assert ds.row_count(legacy) == 1


def test_read_can_project_columns_and_select_countries(tmp_path):
    root = tmp_path / "decisions"
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(_frame([("h1", "fiji", "01.1.1"), ("h2", "samoa", "01.1.2")]))

    only = ds.read(root, columns=["input_hash"], countries=["fiji"])
    assert list(only.columns) == ["input_hash"]
    assert list(only["input_hash"]) == ["h1"]


def test_read_missing_table_is_empty_not_an_error(tmp_path):
    assert ds.read(tmp_path / "nothing.parquet").empty
    assert ds.row_count(tmp_path / "nothing.parquet") == 0


def test_write_can_partition_by_a_key_the_frame_does_not_carry(tmp_path):
    """classified.parquet's column list is a contract; the key rides alongside."""
    root = tmp_path / "classified"
    schema = pa.schema([("input_hash", pa.string()), ("coicop_code", pa.string())])
    view = pd.DataFrame(
        {"input_hash": ["h1", "h2"], "coicop_code": ["01.1.1", "01.1.2"]}
    )
    with ds.PartitionedWriter(root, schema) as w:
        w.write(view, countries=pd.Series(["fiji", "samoa"]))

    assert ds.existing_countries(root) == {"fiji", "samoa"}
    fiji = pd.read_parquet(root / "fiji.parquet")
    assert list(fiji.columns) == ["input_hash", "coicop_code"]
    assert list(fiji["input_hash"]) == ["h1"]


def test_write_projects_away_extra_columns(tmp_path):
    root = tmp_path / "t"
    schema = pa.schema([("input_hash", pa.string())])
    frame = pd.DataFrame({"input_hash": ["h1"], "country": ["fiji"], "junk": [1]})
    with ds.PartitionedWriter(root, schema) as w:
        w.write(frame)
    assert list(pd.read_parquet(root / "fiji.parquet").columns) == ["input_hash"]


def test_non_contiguous_countries_group_correctly(tmp_path):
    """groupby on a positional key must not misalign against a non-range index."""
    root = tmp_path / "t"
    frame = _frame([("h1", "fiji", "a"), ("h2", "samoa", "b"), ("h3", "fiji", "c")])
    frame.index = [10, 20, 30]
    with ds.PartitionedWriter(root, SCHEMA) as w:
        w.write(frame)
    assert sorted(pd.read_parquet(root / "fiji.parquet")["input_hash"]) == ["h1", "h3"]
    assert list(pd.read_parquet(root / "samoa.parquet")["input_hash"]) == ["h2"]
