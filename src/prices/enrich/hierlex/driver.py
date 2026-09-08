"""Full-corpus, memory-bounded, resumable HierLex scoring, across processes.

Walks the embed store bucket by bucket, several buckets at a time. A bucket's
vectors are gathered at NAME grain and then indexed out to the (name, country)
pairs that bucket carries, so the 1.8% pair overhead costs scoring but no extra
I/O. Each bucket lands as its own parquet shard, so a run that dies at bucket
200 resumes at bucket 200 -- and so workers never have to talk to each other.

The pool is memory-bound, not core-bound, and the two things that made it
possible are both about resident bytes rather than about scheduling. The corpus
pair table is ~20 GB, so it is built in a process that exits before any worker is
forked (`_stage_pairs`). And a whole bucket's matrix is ~9 GB with its
transients, so a worker gathers one scoring chunk at a time instead
(`_score_bucket`). Together those put a worker near 4 GB, which is what turns
"two workers" into "as many as the budget holds".

Shards are policy-independent: they carry `calibrated_correctness_score`, and
acceptance is a threshold comparison applied downstream. Switching between
`conservative_risk` and `empirical_98` therefore re-reads shards rather than
re-scoring, and only a new bundle version invalidates them.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from prices import partition
from prices.enrich import config
from prices.enrich.classifier import bucket_pool, embed_store, fingerprint
from prices.enrich.hierlex import scorer as hlx_scorer
from prices.enrich.hierlex import vectors

PRED_ROOT = config.PRODUCTS_INPUT_PARQUET.parent / "_hierlex_pred"
PAIR_COLS = ["product_name_original", "country"]

# What one scoring process costs, measured on this box against the production
# store (133k names per bucket, three blocks, 7,680-d):
#
#   scorer.load()            1.65 GB, resident for the whole life of the worker
#   embed_store.gather()     the largest block's bucket, whole, however few names
#                            are asked for -- it dicts the npz before selecting
#   the gather result        ~50 kB per name: the fp32 matrix plus the hstack
#                            that builds it, both live at once
#
# The last term is why a WHOLE bucket at a time is unaffordable. 128k names is
# 3.9 GB of matrix and another 3.4 GB of transient, so a worker peaks near 9 GB
# and two of them do not leave room for anything else on a 26 GB box. That is
# what kept this loop serial. Gathering a scoring chunk at a time bounds a
# worker by the chunk instead, at the price of re-reading the bucket's npz once
# per chunk (~1.5 s against ~10 s of scoring).
SCORER_BYTES = int(1.65 * 1024**3)
GATHER_BYTES_PER_ROW = vectors.DIM * 4 * 2  # the fp32 result + the hstack of it
GATHER_ROWS = 20_000


def pair_table(products: pd.DataFrame) -> pd.DataFrame:
    """Unique (name, country) rows — the grain HierLex scores at."""
    df = pd.DataFrame(
        {
            "name": products["product_name_original"].astype(str),
            "country": products["country"].fillna("missing").astype(str).str.lower(),
        }
    )
    return df.drop_duplicates(ignore_index=True)


def _shard_state(
    part: Path, pairs: pd.DataFrame, fp: dict
) -> tuple[pd.DataFrame | None, pd.DataFrame, set[str] | None]:
    """What of `pairs` this shard already covers, and what is left to score.

    Returns `(cached, todo)`:

      - `(None, pairs, None)` — no usable shard. Score the bucket from scratch.
      - `(df, empty, unemb)`  — full hit. Today's fast path.
      - `(df, todo, unemb)`   — partial hit. Score ONLY `todo` and append.

    `unemb` is reported for a reused bucket because otherwise a fully-cached run
    reports zero unembedded names whatever the backlog actually is, and that
    number is the one used to decide whether the store is complete.

    A fingerprint mismatch is the first case, never the third. Appending rows
    scored under one embed recipe to rows scored under another produces a shard
    that is internally inconsistent and carries no sign of it.

    `_score_bucket` drops pairs whose name the embed store does not cover, so a
    shard never contains them. Demanding them back made this check fail for every
    bucket carrying even one such name -- which is all of them, at ~800 per
    bucket -- and the documented resume silently rescored from zero. Compare
    against the pairs the scorer would actually have written.
    """
    if not part.exists():
        return None, pairs, None
    if not fingerprint.matches(part, fp):
        print(f"[hierlex] {part.name} fingerprint mismatch — rescoring", flush=True)
        return None, pairs, None
    try:
        df = pd.read_parquet(part)
    except Exception:
        return None, pairs, None
    if "calibrated_correctness_score" not in df.columns:
        return None, pairs, None

    have = set(zip(df["name"].astype(str), df["country"].astype(str)))
    _, unembedded = vectors.split_by_store_coverage(pairs["name"].unique().tolist())
    scorable = pairs[~pairs["name"].astype(str).isin(unembedded)]
    keys = list(zip(scorable["name"].astype(str), scorable["country"].astype(str)))
    mask = np.fromiter((k not in have for k in keys), dtype=bool, count=len(keys))
    return df, scorable[mask], unembedded


def _score_bucket(
    scorer,
    bucket: int,
    pairs: pd.DataFrame,
    chunk_rows: int,
    gather_rows: int = 0,
) -> tuple[pd.DataFrame, set[str]]:
    """Score one bucket's pairs, materializing vectors `gather_rows` at a time.

    `gather_rows=0` gathers the whole bucket into one matrix, which is what this
    did before. Any positive value splits the SAME sequence of pairs into
    coarser runs and gathers only the names a run needs, so a worker's peak is
    set by the run rather than by the bucket -- the difference between ~9 GB and
    ~4 GB, and therefore between two workers and five.

    The output is unchanged row for row, not merely equivalent. The gather split
    is strictly coarser than the `chunk_rows` split, so the chunks handed to
    `scorer.score` are the same runs of the same rows in the same order; and
    every step of that call is per-row -- `finalize_block` normalizes each row
    against itself, and nothing downstream of it looks across the batch. A name
    in two countries that straddles a run boundary is gathered twice, which
    costs the 1.8% pair overhead once more and nothing else.
    """
    names = pairs["name"].unique().tolist()
    _, unembedded = vectors.split_by_store_coverage(names)
    usable = [n for n in names if n not in unembedded]
    todo = pairs[pairs["name"].isin(usable)]
    if todo.empty:
        return pd.DataFrame(), unembedded

    nm, ct = todo["name"].to_numpy(), todo["country"].to_numpy()
    # Never finer than a scoring chunk: a gather smaller than the chunk it feeds
    # would re-read the bucket mid-chunk and buy nothing back.
    span = max(chunk_rows, gather_rows) if gather_rows else len(todo)

    out = []
    for g in range(0, len(todo), span):
        want = list(pd.unique(nm[g : g + span]))
        mat = vectors.matrix_for_bucket(bucket, want)
        row_of = {n: i for i, n in enumerate(want)}
        for s in range(g, min(g + span, len(todo)), chunk_rows):
            sl = slice(s, s + chunk_rows)
            idx = np.fromiter(
                (row_of[n] for n in nm[sl]), dtype=np.int64, count=len(nm[sl])
            )
            out.append(scorer.score(nm[sl], ct[sl], mat[idx]))
        del mat
    return pd.concat(out, ignore_index=True), unembedded


def _stage_pairs(
    products_path: Path, stage_dir: Path, max_buckets: int | None
) -> dict[int, int]:
    """Split the corpus into one small pairs file per bucket; report the counts.

    This is the whole reason a pool is affordable. `pair_table` over the corpus
    is 32.7M rows and ~20 GB resident, and `del` does not hand that back to the
    OS: the frame is tens of millions of python strings out of pymalloc arenas,
    and a freed arena stays mapped to the process. Forking workers from a parent
    still holding those pages is what OOM-killed the run in a952fa04 --
    copy-on-write is no defence, because refcounting writes to the header of
    every object a child so much as reads.

    So the frame is built in a process that then exits, which returns the pages
    unconditionally, and each worker reads back only the bucket it was handed.
    """
    products = pd.read_parquet(products_path, columns=PAIR_COLS)
    pairs = pair_table(products)
    del products

    pairs["bucket"] = [embed_store.bucket_of(n) for n in pairs["name"]]
    keep = set(sorted(pairs["bucket"].unique().tolist())[:max_buckets or None])
    stage_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[int, int] = {}
    for b, g in pairs.groupby("bucket", sort=True):
        b = int(b)
        if b not in keep:
            continue
        part = stage_dir / f"pairs_{b:03d}.parquet"
        tmp = part.with_suffix(".parquet.tmp")
        g[["name", "country"]].to_parquet(tmp, index=False)
        tmp.replace(part)
        counts[b] = len(g)
    return counts


def _stage(
    products_path: Path, stage_dir: Path, max_buckets: int | None
) -> dict[int, int]:
    """`_stage_pairs` in a child, so the parent that forks the pool is small."""
    with ProcessPoolExecutor(max_workers=1) as pool:
        return pool.submit(_stage_pairs, products_path, stage_dir, max_buckets).result()


def _worker_bytes(buckets: Sequence[int], gather_rows: int) -> int:
    """Peak resident bytes of one scoring process.

    The bucket term is the LARGEST single block, not the sum of the three:
    `matrix_for_bucket` loads one block, finalizes it and drops it before
    touching the next, so their fp16 buckets never coexist. What does coexist is
    the gather result and the hstack building it, which is the per-row term.
    """
    tags = [b["tag"] for b in config.CLASSIFIER_EMBED_ENSEMBLE]
    widest = max(
        (bucket_pool.bucket_bytes(b, [t]) for b in buckets for t in tags), default=0
    )
    return SCORER_BYTES + widest + gather_rows * GATHER_BYTES_PER_ROW


def _plan_workers(requested: int, buckets: Sequence[int], gather_rows: int) -> int:
    """How many scoring processes fit the memory budget. Never fewer than one.

    Cores are not the limit and never were: this box has sixteen and room for
    about five. Asking for more gets you fewer, printed, rather than an OOM --
    and an OOM here is expensive, because the killer picks the biggest process
    and every worker is the same size.
    """
    per = _worker_bytes(buckets, gather_rows)
    budget = bucket_pool.budget_bytes()
    fits = int(budget // per) or 1
    n = max(1, min(requested, fits, len(buckets) or 1, os.cpu_count() or 1))
    if n < requested:
        print(
            f"[hierlex] {requested} workers requested, running {n}: "
            f"{per / 1e9:.1f} GB each against a {budget / 1e9:.1f} GB budget",
            flush=True,
        )
    return n


# One loaded bundle per worker process, not one per bucket: `scorer.load` is
# 1.65 GB and seven seconds, which is a fifth of a bucket's scoring time.
_LOADED: tuple | None = None


def _resident_scorer(version: str | None):
    global _LOADED
    if _LOADED is None or _LOADED[0] != version:
        _LOADED = (version, hlx_scorer.load(version))
    return _LOADED[1]


def _run_bucket(job: dict) -> dict:
    """Score (or reuse) one bucket and write its shard. This is the worker.

    Resume is decided HERE, per bucket, and not by the parent, which is what
    keeps it identical to the sequential path: `_shard_state` reads the shard
    the worker is about to write and rules on the very pairs it is about to
    score. The bundle is loaded only after that ruling, so a fully cached resume
    never loads a model in any process.
    """
    b = job["bucket"]
    pairs = pd.read_parquet(job["pairs_path"])
    part = job["out_dir"] / f"pred_{b:03d}.parquet"
    cached, todo, cached_unemb = _shard_state(part, pairs, job["fp"])
    if cached is not None and todo.empty:
        return {
            "bucket": b,
            "pairs": len(pairs),
            "cached": True,
            "appended": False,
            "scored": 0,
            "unembedded": len(cached_unemb or ()),
        }

    df, unembedded = _score_bucket(
        _resident_scorer(job["version"]),
        b,
        todo,
        job["chunk_rows"],
        job["gather_rows"],
    )
    # A partial hit already screened the WHOLE bucket; `_score_bucket` only saw
    # `todo`, so its count would miss names the cached half covers.
    n_unembedded = len(cached_unemb if cached_unemb is not None else unembedded)
    scored = len(df)
    if cached is not None:
        # Append. The bucket's own rows only -- `cached` was already proven to
        # carry this fingerprint, so the two halves share a vector space.
        df = pd.concat([cached, df], ignore_index=True)
    if not df.empty:
        tmp = part.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(part)
        fingerprint.write(part, job["fp"])
    return {
        "bucket": b,
        "pairs": len(pairs),
        "cached": False,
        "appended": cached is not None,
        "scored": scored,
        "unembedded": n_unembedded,
    }


def run(
    version: str | None = None,
    chunk_rows: int = 20_000,
    max_buckets: int | None = None,
    products_path: Path | None = None,
    pred_root: Path = PRED_ROOT,
    workers: int = 1,
    gather_rows: int = GATHER_ROWS,
) -> dict:
    """Score every (name, country) pair in `products_input` into shards."""
    from prices.enrich.hierlex import package  # noqa: PLC0415

    products_path = products_path or config.PRODUCTS_INPUT_PARQUET
    # Resolved from the manifest rather than by loading the bundle. `out_dir` is
    # the only thing the parent wants the version for, and a parent that loads
    # 1.65 GB of models it will never score with pays for that again in every
    # process it forks.
    resolved = package.manifest(package.resolve(version))["method_version"]
    out_dir = pred_root / resolved
    out_dir.mkdir(parents=True, exist_ok=True)
    # Computed once: it reads the bundle manifest, and it is identical for every
    # bucket in the run by construction.
    fp = fingerprint.current(version=version, scorer_version=resolved)

    stage_dir = out_dir / "_pairs"
    counts = _stage(products_path, stage_dir, max_buckets)
    buckets = sorted(counts)
    total = sum(counts.values())
    n_workers = _plan_workers(workers, buckets, gather_rows)

    jobs = [
        (
            _worker_bytes([b], gather_rows),
            {
                "bucket": b,
                "pairs_path": stage_dir / f"pairs_{b:03d}.parquet",
                "out_dir": out_dir,
                "version": version,
                "fp": fp,
                "chunk_rows": chunk_rows,
                "gather_rows": gather_rows,
            },
        )
        for b in buckets
    ]

    tally = {"i": 0, "done": 0, "cached": 0, "appended": 0, "scored": 0, "unemb": 0}
    t0 = time.monotonic()

    def report(r: dict) -> None:
        """One line per finished bucket, printed in the PARENT as it lands.

        Completion order stops being bucket order the moment there is more than
        one worker, so the line leads with the bucket it is about and the
        counter counts buckets finished. A three-hour run is monitored by this
        output; a pool that swallows it into a future is not an improvement.
        """
        tally["i"] += 1
        tally["done"] += r["pairs"]
        tally["unemb"] += r["unembedded"]
        if r["cached"]:
            tally["cached"] += 1
            print(
                f"[hierlex] bucket {r['bucket']:3d} cached ({r['pairs']} pairs)",
                flush=True,
            )
            return
        tally["appended"] += int(r["appended"])
        tally["scored"] += r["scored"]
        el = time.monotonic() - t0
        eta = el / max(tally["done"], 1) * (total - tally["done"])
        print(
            f"[hierlex] bucket {r['bucket']:3d} ({tally['i']}/{len(buckets)}) "
            f"scored {r['scored']} pairs, {r['unembedded']} names unembedded — "
            f"{tally['done']:,}/{total:,} "
            f"elapsed {el / 60:.0f}m eta {eta / 60:.0f}m",
            flush=True,
        )

    # Buckets are independent -- a name's bucket is sha1(name)[:4] % 256, so no
    # two workers want the same store file and no state crosses between them --
    # and each writes its own shard, so a pool that dies loses only what was in
    # flight. `run_budgeted` is used for the byte admission on top of the worker
    # count, and because it delivers every finished unit to `report` even on a
    # run that ends in failure.
    partition.run_budgeted(
        jobs,
        _run_bucket,
        workers=n_workers,
        budget=bucket_pool.budget_bytes(),
        on_result=report,
    )

    return {
        "version": resolved,
        "pairs": int(total),
        "buckets": len(buckets),
        # The three numbers that say whether the cache did anything. A run that
        # reports buckets_appended == 0 and pairs_scored == pairs did a full
        # rescore, whatever the wall clock suggests.
        "buckets_cached": tally["cached"],
        "buckets_appended": tally["appended"],
        "pairs_scored": int(tally["scored"]),
        "unembedded_names": tally["unemb"],
        "shards": str(out_dir),
        "workers": n_workers,
    }


# What the two callers of `load_shards` actually read. `backends._score_hierlex`
# takes the first eight to build its ScoreResult frame; `hierlex report` adds
# `is_fallback`. The scorer writes thirteen -- raw_correctness_score,
# parent_pred, parent_score and script are diagnostics no consumer touches, and
# reading them costs I/O and resident bytes on every one of the 256 parts.
LOAD_COLUMNS = (
    "name",
    "country",
    "assigned_coicop",
    "proposed_leaf",
    "is_leaf",
    "original_score",
    "calibrated_correctness_score",
    "accepted",
    "is_fallback",
)


def load_shards(
    version: str | None = None,
    pred_root: Path = PRED_ROOT,
    columns: Sequence[str] | None = LOAD_COLUMNS,
) -> pd.DataFrame:
    """Every scored pair for a bundle version, concatenated.

    `columns` defaults to what the callers read rather than to everything, so
    the diagnostic columns are not paid for. Pass None for the full frame."""
    from prices.enrich.hierlex import package

    version = version or package.manifest(package.resolve(version))["method_version"]
    parts = sorted((pred_root / version).glob("pred_*.parquet"))
    if not parts:
        raise FileNotFoundError(
            f"no HierLex shards under {pred_root / version} — run `prices hierlex score`"
        )
    wanted = list(columns) if columns else None
    return pd.concat(
        (pd.read_parquet(p, columns=wanted) for p in parts), ignore_index=True
    )
