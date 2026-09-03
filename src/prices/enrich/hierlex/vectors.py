"""Materialize production-weighted 7,680-d vectors out of the local embed store.

The bundle's own loader wants a directory of three whole-block `.npz` files with
a `names` column, and builds a python dict over every name in them. Our store is
256 sharded buckets per block keyed by a length-prefixed blob, holds 7.1M names,
and is 118 GB — so it is read a bucket at a time and never materialized whole.

The two sides agree exactly on what a vector means, which is what makes this a
substitution rather than a reimplementation: identical block order
(4b -> 8b -> arctic), identical dims (2560/4096/1024), identical weights
(2.0/4.0/0.5), per-block L2 before the weight, and no renormalization after the
concatenation. `embedding.finalize_block` is the in-house half of that contract;
skipping it would feed unweighted columns to a model fitted on weighted ones.
"""

from __future__ import annotations

import numpy as np

from prices.enrich import config, embedding
from prices.enrich.classifier import embed_store

DIM = sum(b["dim"] for b in config.CLASSIFIER_EMBED_ENSEMBLE)


def matrix_for_bucket(bucket: int, names: list[str]) -> np.ndarray:
    """(len(names), 7680) float32. Every name must be present in every block."""
    return np.hstack(
        [
            embedding.finalize_block(blk, embed_store.gather(blk["tag"], bucket, names))
            for blk in config.CLASSIFIER_EMBED_ENSEMBLE
        ]
    )


def matrix_for_names(names) -> np.ndarray:
    """Same, for an arbitrary name list spanning buckets, in the given order.

    Touches one bucket per block per distinct bucket in `names`, so it is for
    samples and parity checks — the full-corpus driver iterates buckets instead.
    """
    names = [str(n) for n in names]
    pos = {n: i for i, n in enumerate(names)}
    out = np.empty((len(names), DIM), dtype=np.float32)
    for b, nm in embed_store.buckets_for(names).items():
        out[[pos[n] for n in nm]] = matrix_for_bucket(b, nm)
    return out


def split_by_store_coverage(names) -> tuple[list[str], set[str]]:
    """Partition names into (embedded, unembedded) against the production store.

    A name is usable only if EVERY block has it, so the unembedded set is the
    union of the per-block misses. Screening is not optional: the bundle CLI's
    `--missing-bundle-action zero` substitutes a zero vector for an unknown name,
    which yields the intercept-only distribution and a gate score that can still
    clear tau — a confident wrong label rather than an error. Reads keys only
    (~10 ms/bucket) instead of paging vectors out of a 118 GB store.
    """
    names = [str(n) for n in names]
    bucket_names = embed_store.buckets_for(names)
    missing: set[str] = set()
    for block in config.CLASSIFIER_EMBED_ENSEMBLE:
        for nm in embed_store.missing_keys(block["tag"], bucket_names).values():
            missing.update(nm)
    embedded = [n for n in names if n not in missing]
    return embedded, missing
