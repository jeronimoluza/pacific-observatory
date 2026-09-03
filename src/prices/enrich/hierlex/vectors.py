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

    Delegates to `embed_store`, which is the single implementation. It arrived
    here and in `stages/classify.py` as two identical copies whose docstrings
    recorded *different* halves of why the screen matters; one copy keeps both.
    """
    return embed_store.split_by_store_coverage(names)
