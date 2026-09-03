"""Full-corpus, memory-bounded, resumable embed → head driver.

Two phases over the durable embedding store (`embed_store.py`):

  1. **Build** — for each ensemble block, embed the names still missing from the
     store, one bucket at a time, appending fp16 vectors. Only ONE mlx model is
     resident at a time (peak ≈ the 8B worker's 7.5 GB) and each model loads once
     per run via the persistent `embedding.MlxWorker`. Already-stored names (a
     resumed run, or a grown corpus's unchanged names) are skipped.

  2. **Predict** — score each bucket's stored vectors with the head, writing
     per-bucket parquet under `_classify_pred/<head_version>/`. Swapping the head
     (a new blessed version) writes a fresh prediction set that reads vectors from
     the store — no re-embedding. A bucket whose stored names no longer cover the
     current corpus names is rescored.

`PRICES_CLASSIFY_MAX_CHUNKS>0` (or `max_chunks`) processes only that many buckets
then raises SystemExit(0) before the caller writes classified.parquet — an ETA
probe that leaves real, resumable store + prediction shards.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config, embedding
from prices.enrich.classifier import MODEL_FILE, bucket_pool, embed_store, version_dir

PRED_DIR = config.PRODUCTS_INPUT_PARQUET.parent / "_classify_pred"


def _build_store(bucket_names: dict[int, list[str]]) -> None:
    for block in config.CLASSIFIER_EMBED_ENSEMBLE:
        tag = block["tag"]
        miss = embed_store.missing(tag, bucket_names)
        if not miss:
            continue
        if block["backend"] == "st":
            for b, nm in miss.items():
                embed_store.append(tag, b, nm, embedding.encode_st_block(block, nm))
                print(f"[embed {tag}] bucket {b} +{len(nm)}", flush=True)
            embedding.free_st()
            continue
        worker = embedding.MlxWorker(block["model"])
        try:
            for b, nm in miss.items():
                t0 = time.monotonic()
                embed_store.append(tag, b, nm, worker.encode(block, nm))
                print(
                    f"[embed {tag}] bucket {b} +{len(nm)} in {time.monotonic() - t0:.0f}s",
                    flush=True,
                )
        finally:
            worker.close()


def _predict_bucket(predictor, tags, b: int, nm: list[str], part: Path) -> pd.DataFrame:
    if part.exists():
        df = pd.read_parquet(part)
        if set(nm).issubset(set(df["name"].astype(str))):
            return df
    x = np.hstack([embed_store.gather(t, b, nm) for t in tags])
    pr = predictor.score_matrix(x, nm)
    df = pd.DataFrame(
        {
            "name": nm,
            "leaf": pd.Series(pr.leaf, dtype=object),
            "conf": pd.Series(pr.conf, dtype=float),
            "accepted": pd.Series(pr.accepted, dtype=bool),
        }
    )
    part.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(part, index=False)
    print(f"[predict {predictor.version}] bucket {b} ({len(nm)} names)", flush=True)
    return df


def _predict_job(item: tuple) -> Path:
    """One bucket, in whichever process picks it up.

    Takes the head *version* rather than the loaded predictor: the bundle is
    sklearn state that would be pickled once per bucket, where reloading it per
    process is cached and paid once. Writes its shard and returns the path —
    nothing large crosses back over the process boundary.
    """
    b, nm, version, tags, pred_dir = item
    from prices.enrich.classifier.predict import load_predictor  # noqa: PLC0415

    part = Path(pred_dir) / f"pred_{b:03d}.parquet"
    _predict_bucket(load_predictor(version), tags, b, nm, part)
    return part


def _model_bytes(version: str) -> int:
    path = version_dir(version) / MODEL_FILE
    return path.stat().st_size if path.exists() else 0


def embed_and_predict(
    predictor,
    uniq,
    pred_root: Path = PRED_DIR,
    max_chunks: int | None = None,
    workers: int = 1,
) -> tuple[dict, dict, dict]:
    """Build the store for `uniq`, then score every name with the head. Returns
    (leaf_by, conf_by, ok_by) maps name -> value.

    `workers` parallelises the predict phase only. Building the store stays
    sequential because it is bound by one resident embedding model, not by
    cores — running four of those at once is how the box runs out of memory,
    not how the run gets faster.
    """
    names = [str(x) for x in uniq]
    bucket_names = embed_store.buckets_for(names)
    cap = (
        max_chunks
        if max_chunks is not None
        else int(os.environ.get("PRICES_CLASSIFY_MAX_CHUNKS", "0") or 0)
    )

    # One capped bucket set drives both build and predict so they never disagree.
    items = sorted(bucket_names.items())
    if cap:
        items = items[:cap]
    _build_store(dict(items))

    pred_dir = pred_root / str(predictor.version)
    tags = [b["tag"] for b in config.CLASSIFIER_EMBED_ENSEMBLE]

    # Fan out over buckets first, then walk them in order below. The second pass
    # is a cache hit per shard, so the ordering, resume and cap semantics stay
    # exactly what they were when this ran one bucket at a time.
    if workers > 1:
        bucket_pool.map_buckets(
            _predict_job,
            [(b, nm, str(predictor.version), tags, str(pred_dir)) for b, nm in items],
            workers=workers,
            tags=tags,
            model_bytes=_model_bytes(str(predictor.version)),
            label="predict",
        )

    leaf_by: dict = {}
    conf_by: dict = {}
    ok_by: dict = {}
    want = set(names)
    for b, nm in items:
        df = _predict_bucket(predictor, tags, b, nm, pred_dir / f"pred_{b:03d}.parquet")
        for n, lf, cf, ac in zip(df["name"], df["leaf"], df["conf"], df["accepted"]):
            n = str(n)
            if n in want:
                leaf_by[n], conf_by[n], ok_by[n] = lf, cf, ac

    if cap:
        print(
            f"[classify] measurement cap: stopped after {len(items)} bucket(s); "
            "store + prediction shards kept, a full run resumes from them",
            flush=True,
        )
        raise SystemExit(0)

    return leaf_by, conf_by, ok_by
