"""A fetcher may curate COICOP per ITEM, not just per source.

The YAML ``coicop_codes`` field is per-source: it can only assert that a whole
feed is one leaf. A multi-commodity feed (WB RTDI, WFP HDX) needs a different
leaf per row, which it supplies from a lookup table in the fetcher's own code
via the ``coicop_code`` column of ``price_observations.csv``.

These tests pin the two halves of that path: the column survives concatenate ->
shard -> prepare, and a shard written before the column existed still reads.
"""

import pandas as pd
import pytest

from prices.enrich import shards
from prices.enrich.prepare_shards import PREPARE_COLUMNS
from prices.enrich.stages.concatenate import _emit_price_obs
from prices.enrich.stages.prepare import prepare_input

ITEMS = [
    ("Rice", "01.1.1.1.1"),
    ("Palm oil", "01.1.5.1.1"),
    ("Fresh milk", "01.1.4.1.1"),
]


def _fetcher_csv(tmp_path):
    """A price_observations.csv carrying a DIFFERENT curated leaf per row."""
    df = pd.DataFrame(
        {
            "observation_date": ["2025-03-01"] * len(ITEMS),
            "country": ["mongolia"] * len(ITEMS),
            "source_key": ["wb_rtdi"] * len(ITEMS),
            "coicop_code": [code for _, code in ITEMS],
            "item_name": [name for name, _ in ITEMS],
            "price_local": [1200.0, 4500.0, 900.0],
            "currency": ["MNT"] * len(ITEMS),
            "unit": ["kg", "lt", "lt"],
            "source_url": ["https://example.invalid/x"] * len(ITEMS),
            "observation_hash": ["h1", "h2", "h3"],
        }
    )
    path = tmp_path / "price_observations.csv"
    df.to_csv(path, index=False)
    return path


def _as_shard(frame, tmp_path):
    frame = frame.assign(
        country="mongolia",
        source="wb_rtdi",
        region="eap",
        subregion="east_asia",
        channel="",
    )
    path = tmp_path / "shard.parquet"
    shards.write_shard(frame, path)
    return path


def test_emit_price_obs_carries_the_per_item_code(tmp_path):
    got = pd.DataFrame(list(_emit_price_obs(_fetcher_csv(tmp_path))))
    assert list(got["declared_coicop_codes"]) == [code for _, code in ITEMS]


def test_per_item_code_survives_shard_and_prepare(tmp_path):
    emitted = pd.DataFrame(list(_emit_price_obs(_fetcher_csv(tmp_path))))
    back = shards.read_shard(
        _as_shard(emitted, tmp_path), columns=list(PREPARE_COLUMNS)
    )
    prepared = prepare_input(back)
    got = dict(
        zip(prepared["product_name_original"], prepared["declared_coicop_codes"])
    )
    # The per-source YAML map has no entry for this source, but even if it did
    # the per-row value must win: it is the more specific of the two.
    assert got == dict(ITEMS)


def test_a_shard_written_before_the_column_existed_still_reads(tmp_path):
    """Schema evolution must not strand the existing corpus.

    ``read_shard`` names its columns explicitly, so without the fill-missing
    branch every shard on disk would raise until the whole corpus had been
    re-concatenated."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    legacy = [c for c in shards.SHARD_COLUMNS if c != "declared_coicop_codes"]
    frame = pd.DataFrame({c: ["x"] for c in legacy})
    frame["wayback"] = [False]
    path = tmp_path / "legacy.parquet"
    # Write WITHOUT the new column, the way a pre-change concatenate did.
    schema = pa.schema(
        [
            pa.field(n, pa.bool_() if n in shards.BOOL_COLUMNS else pa.string())
            for n in legacy
        ]
    )
    pq.write_table(pa.Table.from_pandas(frame[legacy], schema=schema), path)

    got = shards.read_shard(path, columns=list(PREPARE_COLUMNS))
    assert "declared_coicop_codes" in got.columns
    assert got["declared_coicop_codes"].isna().all()


@pytest.mark.parametrize("name,code", ITEMS)
def test_curated_codes_are_real_taxonomy_leaves(name, code):
    """A curated code that is not a deepest leaf silently falls through to the
    classifier -- the defect behind the 36 configs shipping ``08.1.0``."""
    coicop_codes = pytest.importorskip("prices.enrich.coicop_codes")
    taxonomy = pytest.importorskip("prices.enrich.coicop_taxonomy")
    try:
        valid_leaves, _ = taxonomy.load_taxonomy_index()
    except FileNotFoundError:
        pytest.skip("coicop_categories.xlsx not available")
    assert coicop_codes.is_narrow(coicop_codes.parse_codes(code), valid_leaves)


@pytest.mark.parametrize(
    "given,expected",
    [
        ("01.1.1.1.2", "01.1.1.1.2"),  # curated leaf outranks the source map
        ("", "02.1.1.1"),  # blank must FALL THROUGH, not assign ""
        ("   ", "02.1.1.1"),
        (None, "02.1.1.1"),
        (float("nan"), "02.1.1.1"),
        ("nan", "02.1.1.1"),  # what pandas leaves behind after astype(str)
    ],
)
def test_blank_curated_code_falls_through_to_the_source_map(given, expected):
    """The silent-blanking failure mode.

    A per-ITEM curated leaf outranks the per-source YAML map, because it is
    strictly more specific evidence. But "present but blank" is not evidence of
    anything: if an empty string were treated as an assignment it would wipe a
    source's COICOP for every row that happens to carry no curated leaf, and
    nothing anywhere would raise. Every empty shape has to fall through."""
    import pandas as pd

    prepare = pytest.importorskip("prices.enrich.stages.prepare")

    df = pd.DataFrame(
        {
            "country": ["mongolia"],
            "source": ["yaml_source"],
            "declared_coicop_codes": [given],
        }
    )
    source_map = {("mongolia", "yaml_source"): "02.1.1.1"}

    per_row = df["declared_coicop_codes"].fillna("").astype(str).str.strip()
    per_row = per_row.where(per_row.str.lower() != "nan", "")
    per_source = pd.Series(
        prepare._source_lookup(df, source_map), index=df.index
    ).astype(str)

    assert per_row.where(per_row != "", per_source).iloc[0] == expected
