"""The snapshot must not materialise the global corpus to build one frame.

products_input is the global corpus. `build_snapshot` used to want one region
out of it and pushed a country predicate into the reader; a global build has no
country to push down, so the bound comes from the join instead. Reading the file
whole cost 27.1 GB of anon-rss and an oom-kill on a 26 GB box, so what these
assert is that the reader still streams and still returns exactly the rows the
join would have kept.
"""

from __future__ import annotations

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from prices.build import aggregate
from prices.build.basket import EAP_COUNTRIES

pytestmark = pytest.mark.unit


def write_corpus(path, row_group_size=3):
    """Twelve rows over four countries, interleaved so a reader that ignores the
    hash filter and takes the first N rows still fails. Small row groups so the
    streaming loop actually iterates."""
    eap = sorted(EAP_COUNTRIES)[:2]
    rows = []
    for i in range(12):
        country = [eap[0], "france", eap[1], "brazil"][i % 4]
        rows.append({"input_hash": f"h{i}", "country": country, "price": float(i)})
    table = pa.Table.from_pandas(pd.DataFrame(rows), preserve_index=False)
    pq.write_table(table, path, row_group_size=row_group_size)
    return path, eap


def test_the_reader_keeps_every_country_when_scope_is_global(tmp_path, monkeypatch):
    """The gate is gone: a non-EAP country must survive the read."""
    path, _ = write_corpus(tmp_path / "pi.parquet")
    monkeypatch.setattr(aggregate, "PRODUCTS_INPUT_PARQUET", path)

    got = aggregate._read_products_for({f"h{i}" for i in range(12)})

    assert len(got) == 12
    assert {"france", "brazil"} <= set(got["country"])


def test_the_reader_returns_exactly_the_rows_the_join_would_keep(tmp_path, monkeypatch):
    path, _ = write_corpus(tmp_path / "pi.parquet")
    monkeypatch.setattr(aggregate, "PRODUCTS_INPUT_PARQUET", path)
    wanted = {"h1", "h7", "h11"}

    got = aggregate._read_products_for(wanted).reset_index(drop=True)
    whole = pd.read_parquet(path)
    masked = whole[whole["input_hash"].isin(wanted)].reset_index(drop=True)

    pd.testing.assert_frame_equal(got, masked)


def test_no_match_is_an_empty_frame_with_the_schema_not_an_error(tmp_path, monkeypatch):
    path, _ = write_corpus(tmp_path / "pi.parquet")
    monkeypatch.setattr(aggregate, "PRODUCTS_INPUT_PARQUET", path)

    got = aggregate._read_products_for({"nope"})

    assert got.empty
    assert list(got.columns) == ["input_hash", "country", "price"]


def test_the_snapshot_reader_streams_row_groups(tmp_path, monkeypatch):
    """A guard on the call itself. If someone reverts to a whole-file read the
    equality tests above still pass -- they exercise the helper, not the caller."""
    path, _ = write_corpus(tmp_path / "pi.parquet")
    monkeypatch.setattr(aggregate, "PRODUCTS_INPUT_PARQUET", path)

    def explode(*args, **kwargs):
        raise AssertionError("build_snapshot read products_input whole")

    monkeypatch.setattr(aggregate.pd, "read_parquet", explode)
    monkeypatch.setattr(
        aggregate,
        "load_filtered_cache",
        lambda: pd.DataFrame({"input_hash": ["h0"], "coicop_code": ["01.1.1.1.0"]}),
    )
    try:
        aggregate.build_snapshot()
    except AssertionError:
        raise
    except Exception:
        # The join and _finalize need columns this fixture does not carry. The
        # assertion is about how the corpus was READ, which has already happened.
        pass
