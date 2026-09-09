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


def test_every_emitted_key_survives_the_spill_projection(tmp_path):
    """`EMITTED_COLS` is a strict projection, and dropping is SILENT.

    `_spill` rebuilds every batch as `{col: ... for col in EMITTED_COLS}`, so a
    key an emitter yields but that is missing from that tuple never reaches the
    shard -- and the column still exists downstream, uniformly null, with
    nothing raised. That is how `declared_coicop_codes` was lost for all 6.14M
    WB RTDI rows: the emitter set it, the tuple did not list it.

    Pinning emitter-keys ⊆ EMITTED_COLS + {wayback} catches the next one."""
    import pandas as pd

    concatenate = pytest.importorskip("prices.enrich.stages.concatenate")

    csv = tmp_path / "price_observations.csv"
    pd.DataFrame(
        [
            {
                "item_name": "Rice (imported)",
                "price_local": 1234.5,
                "currency": "KES",
                "observation_date": "2024-01-01",
                "source_url": "https://example.invalid/catalog/4483",
                "observation_hash": "abc123",
                "coicop_code": "01.1.1.1.2",
                "unit": "KG",
            }
        ]
    ).to_csv(csv, index=False)

    emitted = list(concatenate._emit_price_obs(csv))
    assert emitted, "the emitter produced no rows"

    allowed = set(concatenate.EMITTED_COLS) | {"wayback"}
    for row in emitted:
        dropped = set(row) - allowed
        assert not dropped, f"emitted keys silently dropped by the spill: {dropped}"

    # and the curated leaf specifically must arrive
    assert emitted[0]["declared_coicop_codes"] == "01.1.1.1.2"


def test_curated_code_survives_all_the_way_into_the_shard(tmp_path, monkeypatch):
    """End-to-end through the real shard writer, because the projections lie.

    A column has to clear TWO separate lists to reach a shard -- EMITTED_COLS
    for the spill, then OUTPUT_COLS for the shard itself -- and clearing only
    one is silent: `_finalise_shard` writes `df[OUTPUT_COLS]` against
    SHARD_SCHEMA, so a column the schema declares but the list omits comes out
    all-null with nothing raised.

    That is not hypothetical. `declared_coicop_codes` cleared the first list and
    not the second, and 6,142,693 WB RTDI rows concatenated into 40 shards with
    every curated COICOP silently gone. Asserting on the emitter alone passed
    the whole time. Only reading the shard back catches it."""
    import pandas as pd

    concatenate = pytest.importorskip("prices.enrich.stages.concatenate")
    shards = pytest.importorskip("prices.enrich.shards")

    country, source = "kenya", "wb_rtdi_prices"
    source_dir = tmp_path / "data" / "ssa" / "east_africa" / country / source
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "item_name": "Rice (imported)",
                "price_local": 1234.5,
                "currency": "KES",
                "observation_date": "2024-01-01",
                "source_url": "https://example.invalid/catalog/4483",
                "observation_hash": "hash-1",
                "coicop_code": "01.1.1.1.2",
                "unit": "KG",
            },
            {
                "item_name": "Maize (white)",
                "price_local": 88.25,
                "currency": "KES",
                "observation_date": "2024-01-01",
                "source_url": "https://example.invalid/catalog/4483",
                "observation_hash": "hash-2",
                "coicop_code": "01.1.1.1.6",
                "unit": "KG",
            },
        ]
    ).to_csv(source_dir / "price_observations.csv", index=False)

    # The price_observations.csv shape is admitted only for a gated manifest.
    monkeypatch.setattr(
        concatenate, "_classifier_csv_map", lambda: {(country, source): "retail"}
    )
    monkeypatch.setattr(concatenate, "_channel_for", lambda c, s: "retail")

    shard_path = tmp_path / "shard.parquet"
    concatenate._write_source_shard(
        source_dir, "ssa", "east_africa", country, source, shard_path
    )

    got = shards.read_shard(shard_path)
    assert len(got) == 2, got
    codes = set(got["declared_coicop_codes"].dropna().astype(str))
    assert codes == {
        "01.1.1.1.2",
        "01.1.1.1.6",
    }, f"curated COICOP lost between the emitter and the shard: {codes}"
    # the sibling column added by the same projection, as a control
    assert set(got["unit"].dropna().astype(str)) == {"KG"}
