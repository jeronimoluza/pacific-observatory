"""The parallel HierLex driver: what it must still do once it forks.

Everything here runs against a real one-block embed store and a fake scorer, so
`matrix_for_bucket`, the bucket arithmetic and the shard/fingerprint handling are
the production ones and only the model is stubbed. The fake's `original_score` is
the row sum of the vector it was handed, which is what makes the equality tests
mean something: a chunked gather that mis-indexed a row would still produce a
frame of the right shape, and only a score tied to the actual vector catches it.

The pool tests assume a `fork` start method, which is what gives the children the
monkeypatched store. Production does not rely on that -- a worker takes its whole
job as a picklable dict and loads the bundle off disk -- but these tests do.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from prices.enrich import config
from prices.enrich.classifier import embed_store
from prices.enrich.hierlex import driver
from prices.enrich.hierlex import scorer as hlx_scorer
from prices.enrich.hierlex import vectors

pytestmark = pytest.mark.unit

DIM = 8
# sha1(name) % 256 spreads these over every bucket, so this is chosen for
# what it leaves in ONE bucket: ~12 names, ~24 pairs, enough that a gather
# span holds repeats and the index into it is not trivially the identity.
NAMES = [f"product {i}" for i in range(3000)]
# Staging and scoring are per bucket and there are 256 of them; the pool
# tests want several buckets, not every bucket.
MAX_BUCKETS = 6


class FakeScorer:
    """Row-wise, like the real one, and traceable back to its input vector."""

    version = "test_v1"

    def score(self, names, countries, x, policy="conservative_risk", batch_size=4096):
        n = len(names)
        return pd.DataFrame(
            {
                "name": np.asarray(names, dtype=object).astype(str),
                "country": np.asarray(countries, dtype=object).astype(str),
                "assigned_coicop": ["01.1.1.1.0"] * n,
                "proposed_leaf": ["01.1.1.1.0"] * n,
                "is_leaf": [True] * n,
                "original_score": x.sum(axis=1).astype(float),
                "calibrated_correctness_score": x[:, 0].astype(float),
                "accepted": [True] * n,
                "is_fallback": [False] * n,
                # A re-batched run would still score every row correctly; this
                # is how a change in chunk COMPOSITION shows up.
                "batch_rows": [n] * n,
            }
        )


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """A one-block store, a fake bundle, and a fresh per-worker scorer cache."""
    from prices.enrich.hierlex import package

    monkeypatch.setattr(embed_store, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(
        config,
        "CLASSIFIER_EMBED_ENSEMBLE",
        [{"tag": "blk", "backend": "store", "dim": DIM, "weight": 1.0}],
    )
    rng = np.random.default_rng(0)
    by_bucket: dict[int, list[str]] = {}
    for n in NAMES:
        by_bucket.setdefault(embed_store.bucket_of(n), []).append(n)
    for b, names in by_bucket.items():
        embed_store.append(
            "blk", b, names, rng.standard_normal((len(names), DIM)).astype(np.float16)
        )

    monkeypatch.setattr(package, "resolve", lambda version=None: tmp_path / "bundle")
    monkeypatch.setattr(
        package, "manifest", lambda pkg: {"method_version": "test_v1", "artifacts": []}
    )
    monkeypatch.setattr(hlx_scorer, "load", lambda version=None: FakeScorer())
    monkeypatch.setattr(driver, "_LOADED", None)
    return tmp_path


@pytest.fixture
def products(tmp_path):
    """Every name in two countries, so pairs outnumber names as they do live.

    Shuffled, and that is load-bearing. Left in name order the two rows of a
    name are adjacent, so a pair's position in the gathered matrix rises
    monotonically with its row and any index into that matrix -- including a
    sorted or otherwise scrambled one -- picks the right vector by accident.
    Real corpora interleave; so does this.
    """
    path = tmp_path / "products_input.parquet"
    frame = pd.DataFrame(
        {
            "product_name_original": [n for n in NAMES for _ in range(2)]
            + [NAMES[0], NAMES[1]],  # duplicates the pair table must collapse
            "country": ["Fiji", "PERU"] * len(NAMES) + ["Fiji", "PERU"],
        }
    )
    frame.sample(frac=1.0, random_state=7).to_parquet(path, index=False)
    return path


# --------------------------------------------------------------------------
# Staging: the step that makes a fork affordable at all.
# --------------------------------------------------------------------------


def test_staging_writes_one_file_per_bucket_and_reports_its_size(
    bundle, products, tmp_path
):
    counts = driver._stage(products, tmp_path / "_pairs", None)

    assert sum(counts.values()) == 2 * len(NAMES)  # the duplicate pairs collapsed
    for b, n in counts.items():
        staged = pd.read_parquet(tmp_path / "_pairs" / f"pairs_{b:03d}.parquet")
        assert len(staged) == n
        assert list(staged.columns) == ["name", "country"]
        assert {embed_store.bucket_of(x) for x in staged["name"]} == {b}
        # `pair_table` lowercases country; the staged file is what the worker
        # scores, so it has to carry that and not the raw value.
        assert set(staged["country"]) <= {"fiji", "peru"}


def test_the_pair_table_is_built_in_a_process_the_parent_never_sees(
    bundle, products, tmp_path, monkeypatch
):
    """The 20 GB frame must not exist in the process that forks the pool.

    `del` does not return it -- freed pymalloc arenas stay mapped -- so the only
    reliable release is a process exit. This asserts the build happened
    somewhere else, which is the property, rather than measuring RSS.
    """
    real = driver.pair_table
    record = tmp_path / "builder.pid"

    def spy(df):
        record.write_text(str(os.getpid()))
        return real(df)

    monkeypatch.setattr(driver, "pair_table", spy)
    driver._stage(products, tmp_path / "_pairs", None)

    assert record.exists(), "pair_table was never called"
    assert int(record.read_text()) != os.getpid()


def test_staging_writes_only_the_buckets_the_run_will_score(bundle, products, tmp_path):
    counts = driver._stage(products, tmp_path / "_pairs", 2)

    assert len(counts) == 2
    assert sorted(counts) == sorted(counts)[:2]
    assert len(list((tmp_path / "_pairs").glob("pairs_*.parquet"))) == 2


# --------------------------------------------------------------------------
# Worker planning: cores are not the limit, memory is.
# --------------------------------------------------------------------------


def test_a_worker_costs_the_model_plus_what_it_gathers_at_once(bundle):
    bare = driver._worker_bytes([0], 0)
    gathering = driver._worker_bytes([0], 20_000)

    assert bare >= driver.SCORER_BYTES
    assert gathering - bare == 20_000 * driver.GATHER_BYTES_PER_ROW


def test_workers_are_clamped_to_what_memory_holds(bundle, monkeypatch):
    """Sixteen cores, a budget that holds two of them."""
    per = driver._worker_bytes([0, 1, 2, 3], 20_000)
    monkeypatch.setattr(driver.bucket_pool, "budget_bytes", lambda: per * 2)

    assert driver._plan_workers(16, [0, 1, 2, 3], 20_000) == 2


def test_a_budget_smaller_than_one_worker_still_runs_one(bundle, monkeypatch):
    monkeypatch.setattr(driver.bucket_pool, "budget_bytes", lambda: 1)

    assert driver._plan_workers(16, [0, 1, 2, 3], 20_000) == 1


def test_never_more_workers_than_buckets(bundle, monkeypatch):
    monkeypatch.setattr(driver.bucket_pool, "budget_bytes", lambda: 1 << 40)

    assert driver._plan_workers(16, [7], 20_000) == 1


# --------------------------------------------------------------------------
# The chunked gather: the change that made a worker fit.
# --------------------------------------------------------------------------


def _bucket_pairs(products_path, bucket):
    products = pd.read_parquet(products_path)
    pairs = driver.pair_table(products)
    return pairs[[embed_store.bucket_of(n) == bucket for n in pairs["name"]]]


def _a_busy_bucket(products_path):
    products = pd.read_parquet(products_path)
    pairs = driver.pair_table(products)
    counts = pd.Series([embed_store.bucket_of(n) for n in pairs["name"]]).value_counts()
    return int(counts.index[0])


def test_a_chunked_gather_scores_identical_rows_in_identical_batches(bundle, products):
    """Gathering per chunk must not change one row of the output.

    The gather split is coarser than the scoring split, so the batches handed to
    the model are the same runs of the same rows -- which is the claim, and the
    only reason the parallel driver is allowed to gather this way.
    """
    b = _a_busy_bucket(products)
    pairs = _bucket_pairs(products, b)
    scorer = FakeScorer()

    whole, unemb_whole = driver._score_bucket(scorer, b, pairs, chunk_rows=4)
    chunked, unemb_chunked = driver._score_bucket(
        scorer, b, pairs, chunk_rows=4, gather_rows=8
    )

    pd.testing.assert_frame_equal(whole, chunked)
    assert unemb_whole == unemb_chunked


def test_the_gather_is_never_finer_than_the_chunk_it_feeds(bundle, products, monkeypatch):
    """A gather smaller than a scoring chunk would re-read the bucket mid-chunk
    and buy back nothing, so it is raised to the chunk."""
    b = _a_busy_bucket(products)
    pairs = _bucket_pairs(products, b)
    calls = []
    real = driver.vectors.matrix_for_bucket
    monkeypatch.setattr(
        driver.vectors,
        "matrix_for_bucket",
        lambda bucket, names: (calls.append(len(names)), real(bucket, names))[1],
    )

    driver._score_bucket(FakeScorer(), b, pairs, chunk_rows=8, gather_rows=1)

    assert calls, "nothing was gathered"
    assert max(calls) > 1


def test_each_scored_row_is_scored_on_its_own_vector(bundle, products):
    """The index from a pair row into the gathered matrix is the one thing the
    chunked gather can get wrong while still producing a well-shaped frame.

    No A/B test can see it: both halves of the comparison run the same indexing,
    so a scrambled index agrees with itself. This checks the score against the
    vector the store independently holds for that row's name -- an absolute
    reading, which is the only kind that catches it.
    """
    b = _a_busy_bucket(products)
    pairs = _bucket_pairs(products, b)
    # Without a repeat inside a span the index is the identity and any
    # permutation of it scores correctly by accident, which would make this
    # assertion vacuous rather than false.
    assert pairs["name"].duplicated().any(), "no name repeats; the index is trivial"

    got, _ = driver._score_bucket(FakeScorer(), b, pairs, chunk_rows=4, gather_rows=8)

    own = {n: float(vectors.matrix_for_bucket(b, [n])[0].sum()) for n in got["name"]}
    assert np.allclose(got["original_score"], [own[n] for n in got["name"]])


def test_a_whole_bucket_gather_is_one_gather(bundle, products, monkeypatch):
    b = _a_busy_bucket(products)
    pairs = _bucket_pairs(products, b)
    calls = []
    real = driver.vectors.matrix_for_bucket
    monkeypatch.setattr(
        driver.vectors,
        "matrix_for_bucket",
        lambda bucket, names: (calls.append(len(names)), real(bucket, names))[1],
    )

    driver._score_bucket(FakeScorer(), b, pairs, chunk_rows=4, gather_rows=0)

    assert len(calls) == 1


# --------------------------------------------------------------------------
# The pool: same shards, same resume, still audible.
# --------------------------------------------------------------------------


def _shards(root):
    return {
        p.name: pd.read_parquet(p) for p in sorted(root.rglob("pred_*.parquet"))
    }


def test_parallel_shards_are_the_shards_the_serial_run_would_have_written(
    bundle, products, tmp_path
):
    serial = driver.run(
        products_path=products,
        pred_root=tmp_path / "serial",
        chunk_rows=4,
        workers=1,
        max_buckets=MAX_BUCKETS,
    )
    parallel = driver.run(
        products_path=products,
        pred_root=tmp_path / "par",
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )

    assert parallel["workers"] > 1, "the pool never forked; the test proves nothing"
    assert serial["pairs"] == parallel["pairs"]
    assert serial["pairs_scored"] == parallel["pairs_scored"]

    a, b = _shards(tmp_path / "serial"), _shards(tmp_path / "par")
    assert a.keys() == b.keys()
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])


def test_a_second_run_reuses_every_shard_and_loads_no_bundle(
    bundle, products, tmp_path, monkeypatch
):
    """Resume is the whole reason the shards exist, and a pool must not lose it.

    The bundle load is booby-trapped rather than counted: a fully cached run has
    no reason to touch a model, and paying 1.65 GB and seven seconds per worker
    to discover there is nothing to score is the regression this catches.
    """
    first = driver.run(
        products_path=products,
        pred_root=tmp_path / "out",
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )
    assert first["buckets_cached"] == 0

    def refuse(version=None):
        raise AssertionError("a cached run must not load the bundle")

    monkeypatch.setattr(hlx_scorer, "load", refuse)
    monkeypatch.setattr(driver, "_LOADED", None)
    second = driver.run(
        products_path=products,
        pred_root=tmp_path / "out",
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )

    assert second["buckets_cached"] == second["buckets"]
    assert second["pairs_scored"] == 0


def test_a_fingerprint_mismatch_rescores_and_never_appends(
    bundle, products, tmp_path, monkeypatch
):
    out = tmp_path / "out"
    driver.run(
        products_path=products,
        pred_root=out,
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )
    shard_dir = out / "test_v1"
    before = _shards(shard_dir)

    # A different vector space under the same bundle version -- the exact case
    # the fingerprint exists for, and the one where appending is unsound.
    monkeypatch.setattr(
        config,
        "CLASSIFIER_EMBED_ENSEMBLE",
        [{"tag": "blk", "backend": "store", "dim": DIM, "weight": 2.0}],
    )
    again = driver.run(
        products_path=products,
        pred_root=out,
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )

    assert again["buckets_cached"] == 0
    assert again["buckets_appended"] == 0
    after = _shards(shard_dir)
    for name in before:
        assert len(after[name]) == len(before[name]), "a rescore must replace, not grow"
        assert not np.allclose(
            after[name]["original_score"], before[name]["original_score"]
        )


def test_a_shard_missing_pairs_is_appended_to_not_rescored(
    bundle, products, tmp_path, monkeypatch
):
    out = tmp_path / "out"
    driver.run(
        products_path=products,
        pred_root=out,
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )
    shard_dir = out / "test_v1"
    part = sorted(shard_dir.glob("pred_*.parquet"))[0]
    full = pd.read_parquet(part)
    kept = full.iloc[:-1]
    kept.to_parquet(part, index=False)

    again = driver.run(
        products_path=products,
        pred_root=out,
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )

    assert again["buckets_appended"] == 1
    assert again["pairs_scored"] == 1
    grown = pd.read_parquet(part)
    assert len(grown) == len(full)
    assert set(zip(grown["name"], grown["country"])) == set(
        zip(full["name"], full["country"])
    )


def test_every_finished_bucket_prints_its_own_line(bundle, products, tmp_path, capsys):
    summary = driver.run(
        products_path=products,
        pred_root=tmp_path / "out",
        chunk_rows=4,
        workers=3,
        max_buckets=MAX_BUCKETS,
    )
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "[hierlex] bucket" in ln]

    assert len(lines) == summary["buckets"]
    assert all("eta" in ln for ln in lines)
    # Out-of-order completion is fine; a line that cannot say which bucket it is
    # about is not, because that is the only way to read a parallel run.
    assert {int(ln.split("bucket")[1].split()[0]) for ln in lines} == set(
        int(p.name[5:8]) for p in (tmp_path / "out" / "test_v1").glob("pred_*.parquet")
    )
