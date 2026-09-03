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
from prices.enrich.classifier import embed_store, fingerprint
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
    # Computed once: it reads the bundle manifest, and it is identical for every
    # bucket in the run by construction.
    fp = fingerprint.current(version=version, scorer_version=scorer.version)

    pairs["bucket"] = [embed_store.bucket_of(n) for n in pairs["name"]]
    groups = sorted(pairs.groupby("bucket", sort=False), key=lambda kv: kv[0])
    if max_buckets:
        groups = groups[:max_buckets]

    total = sum(len(g) for _, g in groups)
    done = 0
    n_unembedded = 0
    n_cached = n_appended = n_scored_pairs = 0
    t0 = time.monotonic()
    for i, (b, g) in enumerate(groups, 1):
        part = out_dir / f"pred_{b:03d}.parquet"
        cached, todo, cached_unemb = _shard_state(part, g, fp)
        if cached is not None and todo.empty:
            done += len(g)
            n_cached += 1
            n_unembedded += len(cached_unemb or ())
            print(f"[hierlex] bucket {b:3d} cached ({len(g)} pairs)", flush=True)
            continue
        df, unembedded = _score_bucket(scorer, b, todo, chunk_rows)
        # A partial hit already screened the WHOLE bucket; `_score_bucket` only
        # saw `todo`, so its count would miss names the cached half covers.
        n_unembedded += len(cached_unemb if cached_unemb is not None else unembedded)
        n_scored_pairs += len(df)
        if cached is not None:
            # Append. The bucket's own rows only -- `cached` was already proven
            # to carry this fingerprint, so the two halves share a vector space.
            n_appended += 1
            df = pd.concat([cached, df], ignore_index=True)
        if not df.empty:
            tmp = part.with_suffix(".parquet.tmp")
            df.to_parquet(tmp, index=False)
            tmp.replace(part)
            fingerprint.write(part, fp)
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
        # The three numbers that say whether the cache did anything. A run that
        # reports buckets_appended == 0 and pairs_scored == pairs did a full
        # rescore, whatever the wall clock suggests.
        "buckets_cached": n_cached,
        "buckets_appended": n_appended,
        "pairs_scored": int(n_scored_pairs),
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
