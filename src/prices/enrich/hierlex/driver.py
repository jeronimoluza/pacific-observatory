"""Full-corpus, memory-bounded, resumable HierLex scoring.

Walks the embed store one bucket at a time. A bucket's vectors are gathered once
at NAME grain (~28k x 7680 float32, ~0.9 GB) and then indexed out to the
(name, country) pairs that bucket carries, so the 1.8% pair overhead costs
scoring but no extra I/O. Each bucket lands as its own parquet shard, so a run
that dies at bucket 200 resumes at bucket 200.

Shards are policy-independent: they carry `calibrated_correctness_score`, and
acceptance is a threshold comparison applied downstream. Switching between
`conservative_risk` and `empirical_98` therefore re-reads shards rather than
re-scoring, and only a new bundle version invalidates them.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config
from prices.enrich.classifier import embed_store
from prices.enrich.hierlex import scorer as hlx_scorer
from prices.enrich.hierlex import vectors

PRED_ROOT = config.PRODUCTS_INPUT_PARQUET.parent / "_hierlex_pred"
PAIR_COLS = ["product_name_original", "country"]


def pair_table(products: pd.DataFrame) -> pd.DataFrame:
    """Unique (name, country) rows — the grain HierLex scores at."""
    df = pd.DataFrame(
        {
            "name": products["product_name_original"].astype(str),
            "country": products["country"].fillna("missing").astype(str).str.lower(),
        }
    )
    return df.drop_duplicates(ignore_index=True)


def _shard_ok(part: Path, pairs: pd.DataFrame) -> pd.DataFrame | None:
    if not part.exists():
        return None
    try:
        df = pd.read_parquet(part)
    except Exception:
        return None
    if "calibrated_correctness_score" not in df.columns:
        return None
    have = set(zip(df["name"].astype(str), df["country"].astype(str)))
    # `_score_bucket` drops pairs whose name the embed store does not cover, so a
    # shard never contains them. Demanding them back made this check fail for
    # every bucket carrying even one such name -- which is all of them, at ~800
    # per bucket -- and the documented resume silently rescored from zero.
    # Compare against the pairs the scorer would actually have written.
    _, unembedded = vectors.split_by_store_coverage(pairs["name"].unique().tolist())
    want = {
        (n, c)
        for n, c in zip(pairs["name"].astype(str), pairs["country"].astype(str))
        if n not in unembedded
    }
    return df if want.issubset(have) else None


def _score_bucket(
    scorer, bucket: int, pairs: pd.DataFrame, chunk_rows: int
) -> tuple[pd.DataFrame, set[str]]:
    names = pairs["name"].unique().tolist()
    _, unembedded = vectors.split_by_store_coverage(names)
    usable = [n for n in names if n not in unembedded]
    todo = pairs[pairs["name"].isin(usable)]
    if todo.empty:
        return pd.DataFrame(), unembedded

    mat = vectors.matrix_for_bucket(bucket, usable)
    row_of = {n: i for i, n in enumerate(usable)}
    idx = np.fromiter(
        (row_of[n] for n in todo["name"]), dtype=np.int64, count=len(todo)
    )

    out = []
    for s in range(0, len(todo), chunk_rows):
        sl = slice(s, s + chunk_rows)
        out.append(
            scorer.score(
                todo["name"].to_numpy()[sl],
                todo["country"].to_numpy()[sl],
                mat[idx[sl]],
            )
        )
    del mat
    return pd.concat(out, ignore_index=True), unembedded


def run(
    version: str | None = None,
    chunk_rows: int = 20_000,
    max_buckets: int | None = None,
    products_path: Path | None = None,
    pred_root: Path = PRED_ROOT,
) -> dict:
    """Score every (name, country) pair in `products_input` into shards."""
    products_path = products_path or config.PRODUCTS_INPUT_PARQUET
    products = pd.read_parquet(products_path, columns=PAIR_COLS)
    pairs = pair_table(products)
    del products

    scorer = hlx_scorer.load(version)
    out_dir = pred_root / scorer.version
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs["bucket"] = [embed_store.bucket_of(n) for n in pairs["name"]]
    groups = sorted(pairs.groupby("bucket", sort=False), key=lambda kv: kv[0])
    if max_buckets:
        groups = groups[:max_buckets]

    total = sum(len(g) for _, g in groups)
    done = 0
    n_unembedded = 0
    t0 = time.monotonic()
    for i, (b, g) in enumerate(groups, 1):
        part = out_dir / f"pred_{b:03d}.parquet"
        cached = _shard_ok(part, g)
        if cached is not None:
            done += len(g)
            print(f"[hierlex] bucket {b:3d} cached ({len(g)} pairs)", flush=True)
            continue
        df, unembedded = _score_bucket(scorer, b, g, chunk_rows)
        n_unembedded += len(unembedded)
        if not df.empty:
            df.to_parquet(part, index=False)
        done += len(g)
        el = time.monotonic() - t0
        eta = el / max(done, 1) * (total - done)
        print(
            f"[hierlex] bucket {b:3d} ({i}/{len(groups)}) scored {len(df)} pairs, "
            f"{len(unembedded)} names unembedded — {done:,}/{total:,} "
            f"elapsed {el / 60:.0f}m eta {eta / 60:.0f}m",
            flush=True,
        )

    return {
        "version": scorer.version,
        "pairs": int(total),
        "buckets": len(groups),
        "unembedded_names": n_unembedded,
        "shards": str(out_dir),
    }


def load_shards(
    version: str | None = None, pred_root: Path = PRED_ROOT
) -> pd.DataFrame:
    """Every scored pair for a bundle version, concatenated."""
    from prices.enrich.hierlex import package

    version = version or package.manifest(package.resolve(version))["method_version"]
    parts = sorted((pred_root / version).glob("pred_*.parquet"))
    if not parts:
        raise FileNotFoundError(
            f"no HierLex shards under {pred_root / version} — run `prices hierlex score`"
        )
    return pd.concat((pd.read_parquet(p) for p in parts), ignore_index=True)
