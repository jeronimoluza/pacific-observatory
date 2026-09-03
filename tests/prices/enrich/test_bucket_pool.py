"""The clamp is the point: more workers than fit must yield fewer workers."""

import numpy as np
import pytest

from prices.enrich.classifier import bucket_pool, embed_store

pytestmark = pytest.mark.unit

GB = 1024**3


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A store with three buckets of deliberately unequal size."""
    monkeypatch.setattr(embed_store, "STORE_DIR", tmp_path)
    for b, n in [(0, 10), (1, 400), (2, 40)]:
        embed_store.append(
            "blk", b, [f"n{b}_{i}" for i in range(n)], np.zeros((n, 64), np.float16)
        )
    return tmp_path


def test_bucket_bytes_sums_every_block(store):
    embed_store.append("other", 1, ["x"], np.zeros((1, 64), np.float16))
    one = bucket_pool.bucket_bytes(1, ["blk"])
    both = bucket_pool.bucket_bytes(1, ["blk", "other"])
    assert one > 0
    assert both > one


def test_a_bucket_a_block_never_embedded_costs_nothing(store):
    assert bucket_pool.bucket_bytes(1, ["never_embedded"]) == 0


def test_worker_cost_is_the_largest_bucket_not_the_average(store):
    """The schedule hands out big buckets first, so an average-sized estimate is
    exactly the number that OOMs."""
    cost = bucket_pool.worker_bytes([0, 1, 2], ["blk"], model_bytes=0)
    biggest = bucket_pool.bucket_bytes(1, ["blk"]) * bucket_pool.GATHER_FACTOR
    assert cost == biggest
    assert cost > bucket_pool.bucket_bytes(2, ["blk"]) * bucket_pool.GATHER_FACTOR


def test_the_model_is_counted_once_per_worker(store):
    bare = bucket_pool.worker_bytes([1], ["blk"], model_bytes=0)
    loaded = bucket_pool.worker_bytes([1], ["blk"], model_bytes=5 * GB)
    assert loaded - bare == 5 * GB


def test_workers_are_clamped_to_the_budget(store):
    """Sixteen cores, a budget that holds two of them."""
    per = bucket_pool.worker_bytes([0, 1, 2], ["blk"], model_bytes=0)
    n = bucket_pool.plan_workers(16, [0, 1, 2], ["blk"], budget=per * 2)
    assert n == 2


def test_a_budget_smaller_than_one_worker_still_runs_one(store):
    n = bucket_pool.plan_workers(16, [0, 1, 2], ["blk"], budget=1)
    assert n == 1


def test_workers_never_exceed_the_buckets_there_are(store):
    per = bucket_pool.worker_bytes([0, 1, 2], ["blk"], model_bytes=0)
    n = bucket_pool.plan_workers(16, [0, 1, 2], ["blk"], budget=per * 100)
    assert n == 3


def test_a_request_for_fewer_workers_is_honoured(store):
    per = bucket_pool.worker_bytes([0, 1, 2], ["blk"], model_bytes=0)
    assert bucket_pool.plan_workers(2, [0, 1, 2], ["blk"], budget=per * 100) == 2


def test_an_explicit_budget_overrides_the_machine(monkeypatch):
    monkeypatch.setattr(bucket_pool.config, "CLASSIFY_MEM_BUDGET_GB", 4.0)
    assert bucket_pool.budget_bytes() == 4 * GB


def test_without_an_explicit_budget_it_is_a_fraction_of_ram(monkeypatch):
    monkeypatch.setattr(bucket_pool.config, "CLASSIFY_MEM_BUDGET_GB", 0.0)
    monkeypatch.setattr(bucket_pool.config, "CLASSIFY_MEM_BUDGET_FRACTION", 0.5)
    monkeypatch.setattr(bucket_pool, "total_memory_bytes", lambda: 100 * GB)
    assert bucket_pool.budget_bytes() == 50 * GB


def record(item):
    """Top-level so the parallel path can pickle it."""
    return (item[0], len(item[1]))


def test_buckets_are_handed_out_longest_first():
    items = [(0, ["a"]), (1, ["a"] * 9), (2, ["a"] * 4)]
    out = bucket_pool.map_buckets(record, items, workers=1)
    assert [b for b, _ in out] == [1, 2, 0]


def test_nothing_to_do_is_not_an_error():
    assert bucket_pool.map_buckets(record, [], workers=4) == []


def test_the_parallel_path_returns_the_same_answers():
    items = [(b, ["a"] * (b + 1)) for b in range(6)]
    seq = bucket_pool.map_buckets(record, items, workers=1)
    par = bucket_pool.map_buckets(record, items, workers=3)
    assert par == seq
