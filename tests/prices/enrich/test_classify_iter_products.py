"""Streaming the corpus must yield exactly what holding it yielded.

The decide loop used to slice a resident 37.4M-row frame with `.iloc`. That
frame is ~20 GB and the run swapped a third of the way through. `iter_products`
reads the same rows from parquet a chunk at a time; if it drifts from
`read_products` the corpus is silently re-projected mid-pipeline, so the
equality is the whole contract.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich.stages import classify

pytestmark = pytest.mark.unit


def write_products(path, n, drop=()):
    cols = {
        "input_hash": [f"h{i}" for i in range(n)],
        "product_name_original": [f"name {i}" for i in range(n)],
        "category": ["cat"] * n,
        "country": ["fiji"] * n,
        "lang": ["en"] * n,
        "details": [""] * n,
        "unit": ["kg"] * n,
        "source": ["shop"] * n,
        "declared_coicop_codes": [""] * n,
        "price": [1.0] * n,  # not in PRODUCT_COLS -- must be projected away
    }
    for c in drop:
        cols.pop(c)
    pd.DataFrame(cols).to_parquet(path, index=False)
    return path


def test_streamed_chunks_equal_the_resident_frame(tmp_path):
    path = write_products(tmp_path / "p.parquet", 10)
    whole = classify.read_products(path)
    streamed = pd.concat(list(classify.iter_products(path, 3)), ignore_index=True)
    pd.testing.assert_frame_equal(whole, streamed)


def test_streaming_projects_away_columns_the_loop_does_not_read(tmp_path):
    path = write_products(tmp_path / "p.parquet", 4)
    chunk = next(classify.iter_products(path, 4))
    assert list(chunk.columns) == classify.PRODUCT_COLS
    assert "price" not in chunk.columns


def test_a_missing_column_is_filled_the_same_way_streamed(tmp_path):
    """`read_products` tolerates a stale products_input by filling absent
    columns with None. The streaming path has to make the same allowance or a
    stale file crashes here instead of degrading visibly."""
    path = write_products(tmp_path / "p.parquet", 6, drop=("unit",))
    whole = classify.read_products(path)
    streamed = pd.concat(list(classify.iter_products(path, 2)), ignore_index=True)
    assert whole["unit"].isna().all()
    pd.testing.assert_frame_equal(whole, streamed)


def test_chunking_does_not_change_the_row_count(tmp_path):
    path = write_products(tmp_path / "p.parquet", 7)
    for size in (1, 2, 3, 7, 100):
        got = sum(len(c) for c in classify.iter_products(path, size))
        assert got == 7, size
