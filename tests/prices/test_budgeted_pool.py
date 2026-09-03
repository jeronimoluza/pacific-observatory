"""Admission by bytes, not by worker count — the rule that keeps the pool alive.

Both prepare and build schedule wildly uneven units over a 26 GB box. A plain
`pool.map` sized by cores OOM-killed prepare 38 seconds in: japan is 3.32 GB of
shard and 13.3 GB resident. These are the arithmetic tests for the fix.
"""

from __future__ import annotations

from prices import partition

GB = 1 << 30


def test_an_idle_pool_admits_a_unit_bigger_than_the_whole_budget():
    # japan is 3.32 GB against a ~3 GB budget. If an oversized unit were
    # refused, nothing would start it and the loop would not terminate.
    assert partition.admits(0, 0, 10 * GB, 1 * GB)


def test_a_busy_pool_refuses_a_unit_that_would_overflow():
    assert not partition.admits(900_000_000, 1, 900_000_000, 1 * GB)


def test_a_busy_pool_admits_a_unit_that_fits():
    assert partition.admits(100_000_000, 1, 100_000_000, 1 * GB)


def test_exactly_filling_the_budget_is_allowed():
    assert partition.admits(500, 1, 500, 1000)
    assert not partition.admits(501, 1, 500, 1000)


def _peak(sizes, workers, budget):
    """Replay the admission loop's arithmetic without starting processes."""
    pending = sorted(sizes, reverse=True)
    inflight: list[int] = []
    peaks = []
    while pending or inflight:
        while pending and len(inflight) < workers:
            if not partition.admits(sum(inflight), len(inflight), pending[0], budget):
                break
            inflight.append(pending.pop(0))
        peaks.append(sum(inflight))
        inflight.pop(0)
    return max(peaks)


def test_the_giants_never_run_together():
    # japan 3.32 GB + taiwan 1.52 GB is the pair that killed the 6-worker run.
    peak = _peak([3_320, 1_520, 550, 530, 10, 10, 10], workers=16, budget=3_000)
    assert peak <= 3_320  # the oversized unit runs alone, nothing joins it


def test_many_small_units_still_fan_out_wide():
    # The budget must not serialize the common case.
    assert _peak([10] * 64, workers=16, budget=3_000) == 160


def test_the_budget_scales_with_free_memory_and_has_a_floor():
    assert partition.memory_budget_bytes() >= 1 * GB
    assert partition.memory_budget_bytes(0.0) == 1 * GB


def test_one_worker_runs_inline_without_a_pool():
    # Below two units or one worker there is nothing to gain from pickling.
    out = partition.run_budgeted([(1, "a"), (2, "b")], str.upper, 1, 10)
    assert out == ["B", "A"]  # largest first


def test_every_job_runs_exactly_once():
    jobs = [(i, i) for i in range(20)]
    out = partition.run_budgeted(jobs, abs, 1, 1000)
    assert sorted(out) == list(range(20))
