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
    worker = aggregate._join_one_shard(str(shard))
    pd.testing.assert_frame_equal(serial, worker)
