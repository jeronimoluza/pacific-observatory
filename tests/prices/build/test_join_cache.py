"""The shard join must stay the merge it replaced.

`_JoinCache` exists only to stop `merge` re-hashing the 2.6M-row cache once per
shard. It is therefore allowed to be faster and nothing else: same rows, same
order, same dtypes. These tests pin that, plus the two cases the fast path
cannot serve on its own -- a duplicated join key, and a bare frame handed
straight to `_join_chunk`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import aggregate

pytestmark = pytest.mark.unit


def _chunk() -> pd.DataFrame:
    """Hits, misses and a repeated key, deliberately not in cache order.

    A chunk whose keys arrive sorted would agree with a merge that silently
    reordered its output, so the interesting orderings have to be in the input.
    """
    return pd.DataFrame(
        {
            "product_name": ["rice", "beans", "salt", "rice", "oil"],
            "product_url": ["u1", "u2", "u3", "u1", "u5"],
            "price": ["1.0", "2.0", "3.0", "1.0", "5.0"],
            "currency": ["FJD"] * 5,
            "country": ["fiji"] * 5,
            "source": ["s"] * 5,
            "date": ["2026-01-01"] * 5,
            "input_hash": ["h3", "hMISS", "h1", "h3", "h2"],
        }
    )


def _cache() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "input_hash": ["h1", "h2", "h3"],
            "coicop_code": ["01.1.1.1.0", "01.1.2.1.0", "01.1.3.1.0"],
            "pricing_basis": ["mass", "volume", "count"],
            "amount_value": [1.0, 2.0, None],
            "trust_level": ["high", "high", "high"],
        }
    )


def _merge_reference(chunk: pd.DataFrame, cache: pd.DataFrame) -> pd.DataFrame:
    """Exactly the expression `_join_chunk` used before `_JoinCache`."""
    merged = chunk.merge(cache, on="input_hash", how="inner", suffixes=("_raw", ""))
    return merged.drop(columns=["input_hash"])


def test_join_cache_reproduces_the_merge_it_replaced():
    chunk, cache = _chunk(), _cache()
    pd.testing.assert_frame_equal(
        aggregate._JoinCache(cache).join(chunk),
        _merge_reference(chunk, cache),
    )


def test_the_hashtable_is_reused_across_chunks():
    """The whole point: one `_JoinCache` serves many chunks and each must give
    the same answer it would have alone. A cache that mutated per join -- by
    consuming its index, say -- would pass the single-chunk test above and fail
    the corpus."""
    cache = _cache()
    joiner = aggregate._JoinCache(cache)
    first = joiner.join(_chunk())
    for _ in range(3):
        pd.testing.assert_frame_equal(joiner.join(_chunk()), first)
    pd.testing.assert_frame_equal(first, _merge_reference(_chunk(), cache))


def test_a_duplicated_key_falls_back_to_merge_and_keeps_the_duplicate():
    """`load_filtered_cache` dedups whole ROWS, so a hash carrying two different
    classifications survives on purpose -- `parity` is where it must surface.
    The fast path cannot represent it (get_indexer needs a unique index), so it
    must hand back to merge rather than pick a winner."""
    cache = pd.concat(
        [_cache(), pd.DataFrame({"input_hash": ["h1"], "coicop_code": ["09.9.9.9.9"]})],
        ignore_index=True,
    )
    joiner = aggregate._JoinCache(cache)
    assert joiner.index is None, "a non-unique key must not take the fast path"

    out = joiner.join(_chunk())
    pd.testing.assert_frame_equal(out, _merge_reference(_chunk(), cache))
    assert (out["coicop_code"] == "09.9.9.9.9").sum() == 1


def test_join_chunk_still_accepts_a_bare_frame():
    """The one-shot callers (and every existing test) pass a DataFrame. Wrapping
    per call is the right cost for them; only the shard loops hoist it."""
    chunk, cache = _chunk(), _cache()
    pd.testing.assert_frame_equal(
        aggregate._join_chunk(chunk, cache),
        aggregate._join_chunk(chunk, aggregate._JoinCache(cache)),
    )


def test_a_non_contiguous_cache_index_still_gathers_the_right_rows():
    """`load_filtered_cache` ends in `drop_duplicates()`, which leaves gaps in
    the frame's index -- while `get_indexer` returns POSITIONS and `.take`
    consumes positions. Mixing the two up returns real rows attached to the
    wrong hashes: a wrong answer, not a crash. So the gap belongs in a fixture
    rather than being assumed away."""
    gappy = pd.concat([_cache(), _cache()], ignore_index=True).iloc[::2]
    assert list(gappy.index) == [0, 2, 4]
    assert gappy["input_hash"].is_unique

    pd.testing.assert_frame_equal(
        aggregate._JoinCache(gappy).join(_chunk()),
        _merge_reference(_chunk(), gappy),
    )
