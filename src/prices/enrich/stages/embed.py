"""Embed stage — put a vector in the store for every name that lacks one.

Embedding used to happen only as a side effect of classify, which made the one
genuinely expensive step in the pipeline invisible: you could not ask how many
names were unembedded, or embed a slice, without running a classification you
did not want. This makes it a stage of its own.

Two backends, and the difference is where the GPU is:

  - **local** encodes in this process (`embedding.py`: sentence-transformers for
    the small block, an mlx subprocess for the large ones). It needs no account
    and no network, and it is the path that always works. It is also slow enough
    that the full corpus is measured in days.
  - **runpod** rents GPUs. That is faster by two orders of magnitude and it is
    also *spending money on someone else's hardware*, so this command stages the
    run — universe file, per-pod bucket plan, the exact commands — and stops.
    Renting the pods stays a decision a person makes, not one a pipeline makes.

Both write the same store, in the same layout, keyed the same way. What they
must NOT share is a block tag: a tag names a vector space, not a model, and the
GPU's bf16 blocks are a different space from the Mac's int8 ones. Mixing them
under one tag interleaves incompatible vectors with nothing to detect it
afterwards, which is why the presets keep `*_bf16` tags distinct.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from prices import partition
from prices.enrich import config, prepare_shards
from prices.enrich.classifier import batch_embed, embed_store

NAME_COL = "product_name_original"
STAGE_DIR = config.ENRICH_DIR / "_embed_staging"


def _prepared_paths(
    selectors: Optional[Sequence[str]], root: Optional[Path]
) -> list[Path]:
    """The prepared country parquets a selector covers.

    Scoping happens on the corpus tree and is mapped to countries, because
    prepare's output is per country while a selector may name a single source.
    """
    shards = partition.select(selectors, root)
    keys = partition.group_by(shards, "country")
    paths = [prepare_shards.prepared_path(key) for key in sorted(keys)]
    return [p for p in paths if p.exists()]


def universe(
    selectors: Optional[Sequence[str]] = None,
    root: Optional[Path] = None,
    products_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Unique names in scope, with the bucket each one belongs to.

    Read from the prepared per-country parquets when they exist, so a scoped
    embed does not have to load the whole corpus union to find the names of one
    country. Falls back to `products_input` when nothing is prepared yet.
    """
    paths = _prepared_paths(selectors, root)
    if paths:
        frame = prepare_shards.read_prepared(paths, columns=[NAME_COL])
    else:
        source = products_path or config.PRODUCTS_INPUT_PARQUET
        if not source.exists():
            return pd.DataFrame({NAME_COL: [], "bucket": []})
        frame = pd.read_parquet(source, columns=[NAME_COL])
    names = pd.Index(frame[NAME_COL].astype(str).unique())
    return pd.DataFrame(
        {NAME_COL: names, "bucket": [embed_store.bucket_of(n) for n in names]}
    )


def missing(names: Sequence[str], tags: Optional[Sequence[str]] = None) -> dict:
    """Per block, how many of these names have no vector yet.

    Reported per block and not as one number because the blocks are embedded
    independently: a run that died after the 8B block leaves the store usable
    for nothing and looking 75% complete.
    """
    tags = tags or [b["tag"] for b in config.CLASSIFIER_EMBED_ENSEMBLE]
    by_bucket = embed_store.buckets_for(names)
    return {
        tag: sum(len(v) for v in embed_store.missing(tag, by_bucket).values())
        for tag in tags
    }


def run_local(names: Sequence[str]) -> dict:
    """Encode everything missing, one block and one bucket at a time.

    Deliberately not parallelised. The cost here is one resident embedding
    model, not CPU: running several at once is how the box runs out of memory,
    not how the run finishes sooner.
    """
    before = missing(names)
    batch_embed._build_store(embed_store.buckets_for(names))
    return {"before": before, "after": missing(names)}


def stage_runpod(
    frame: pd.DataFrame, pods: int = 1, out_dir: Optional[Path] = None
) -> dict:
    """Write what a fleet run needs, and return the commands to start it.

    Stops short of launching. A pod is billed by the hour from the moment it
    exists, so the last step stays manual on purpose.
    """
    out_dir = out_dir or STAGE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    universe_path = out_dir / "embed_universe.parquet"
    frame.to_parquet(universe_path, index=False)

    kit = Path("src/prices/enrich/gpu")
    return {
        "universe": universe_path,
        "names": len(frame),
        "pods": pods,
        "commands": [
            f"EMBED_UNIVERSE={universe_path} PYTHONPATH=src python "
            f"{kit}/fleet/plan.py --pods {pods} > {kit}/fleet/pods.txt",
            f"{kit}/fleet/setup.sh",
            f"EMBED_UNIVERSE={universe_path} {kit}/fleet/launch.sh",
            f"{kit}/fleet/monitor.sh",
            f"{kit}/fleet/download.sh",
        ],
    }


def run(
    backend: str = "local",
    selectors: Optional[Sequence[str]] = None,
    root: Optional[Path] = None,
    pods: int = 1,
    out_dir: Optional[Path] = None,
) -> dict:
    frame = universe(selectors, root)
    names = frame[NAME_COL].tolist()
    gaps = missing(names)
    print(f"[embed] {len(names)} names in scope")
    for tag, n in gaps.items():
        print(f"[embed]   {tag}: {n} without a vector")
    if not any(gaps.values()):
        return {"names": len(names), "missing": gaps, "backend": backend}

    if backend == "local":
        return {"names": len(names), "backend": backend, **run_local(names)}
    if backend == "runpod":
        staged = stage_runpod(frame, pods=pods, out_dir=out_dir)
        print(f"[embed] staged {staged['names']} names for {pods} pod(s)")
        print("[embed] nothing has been rented. To start the fleet:")
        for cmd in staged["commands"]:
            print(f"    {cmd}")
        return {"names": len(names), "missing": gaps, "backend": backend, **staged}
    raise ValueError(f"unknown embed backend {backend!r}; have 'local', 'runpod'")
