"""The parallel observations join must be the serial one, not a second one."""

from __future__ import annotations

import pandas as pd

from prices.build import aggregate


def test_the_worker_join_matches_the_serial_join(tmp_path, monkeypatch):
    """Both paths funnel through the same `_join_chunk`. If they did not, the
    parallel build would be a second implementation free to drift from the one
    the reference set was captured with."""
    shard = tmp_path / "s.parquet"
    pd.DataFrame(
        {
            "product_name": ["rice", "beans"],
            "product_url": ["u1", "u2"],
            "price": ["1.0", "2.0"],
            "currency": ["FJD", "FJD"],
            "country": ["fiji", "fiji"],
            "source": ["s", "s"],
            "date": ["2026-01-01", "2026-01-01"],
            "input_hash": ["h1", "h2"],
        }
    ).to_parquet(shard, index=False)

    cache = pd.DataFrame(
        {
            "input_hash": ["h1"],
            "coicop_code": ["01.1.1.1.0"],
            "state": ["classified"],
            "trust_level": ["high"],
        }
    )

    serial = aggregate._join_chunk(
        aggregate.shard_io.read_shard(
            shard, columns=list(aggregate.RAW_OBSERVATION_COLS)
        ),
        cache,
    )
    monkeypatch.setattr(aggregate, "_WORKER_CACHE", cache)
    worker = aggregate._join_one_shard((str(shard), None))
    pd.testing.assert_frame_equal(serial, worker)


def test_a_row_group_split_reads_the_same_rows_as_the_whole_shard(tmp_path):
    """Splitting a shard by row group must be a pure change of granularity.

    The whole reason units are split is that one 2.85 GB shard was an
    indivisible job larger than the admission budget, so it ran alone and still
    killed its worker. That fix is only safe if reading a file in pieces yields
    exactly the file -- a split that dropped or reordered rows would show up as
    a quietly smaller corpus, not as an error.
    """
    shard = tmp_path / "big.parquet"
    frame = pd.DataFrame(
        {
            "product_name": [f"item {i}" for i in range(600)],
            "product_url": [f"u{i}" for i in range(600)],
            "price": [str(float(i)) for i in range(600)],
            "currency": ["FJD"] * 600,
            "country": ["fiji"] * 600,
            "source": ["s"] * 600,
            "date": ["2026-01-01"] * 600,
            "input_hash": [f"h{i}" for i in range(600)],
        }
    )
    frame.to_parquet(shard, index=False, row_group_size=100)

    cols = list(aggregate.RAW_OBSERVATION_COLS)
    whole = aggregate.shard_io.read_shard(shard, columns=cols)
    pieces = [
        aggregate.shard_io.read_shard_row_groups(shard, group, columns=cols)
        for group in ([0, 1], [2, 3], [4, 5])
    ]
    pd.testing.assert_frame_equal(whole, pd.concat(pieces, ignore_index=True))


def test_splitting_is_confined_to_shards_over_the_target(tmp_path):
    """A shard under the target stays one unit, and no bytes go missing.

    Sizes stay denominated in on-disk bytes because `run_budgeted` admits work
    by them; a split unit that misreported its share would corrupt the very
    admission rule the split exists to satisfy.
    """
    small = tmp_path / "small.parquet"
    pd.DataFrame({"a": range(10)}).to_parquet(small, index=False)

    class _Shard:
        def __init__(self, path, size):
            self.path = path
            self.size = size

    shard = _Shard(small, small.stat().st_size)
    units = list(aggregate._shard_units([shard], target=10**9))
    assert units == [(shard.size, (str(small), None))]

    # One row group is indivisible, so it stays one unit however small the
    # target. Splitting is a granularity the file has to offer, not one the
    # planner can invent.
    assert list(aggregate._shard_units([shard], target=1)) == units

    many = tmp_path / "many.parquet"
    pd.DataFrame({"a": range(600)}).to_parquet(
        many, index=False, row_group_size=100
    )
    wide = _Shard(many, many.stat().st_size)
    split = list(aggregate._shard_units([wide], target=1))
    assert len(split) > 1
    assert all(payload[1] is not None for _, payload in split)
    assert sum(size for size, _ in split) <= wide.size
