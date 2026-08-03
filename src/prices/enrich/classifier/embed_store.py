"""Durable, name-keyed, fp16 ensemble-embedding store.

Embedding the ~1.5M-name corpus through 0.6B+4B+8B is the expensive, STABLE part
of classify; the logistic head is cheap and changes often (new gold, new C,
recalibrated tau). So the per-block, per-row-L2 vectors are persisted ONCE as
float16 (~24 GB) and any head scores over them without re-embedding. Growing the
corpus embeds only the new names; swapping the head only re-runs prediction.

Layout: ``_embed_store/<tag>/bucket_<b>.npz`` with ``keys`` (names) and ``mat``
(fp16 (n, dim)). A name hashes to a fixed bucket (stable across corpus versions),
so a bucket holds every name ever embedded for it; build appends only the missing
ones, and both build and read touch one bucket at a time (bounded memory). fp16
is upcast to fp32 on read — a ~5e-4 relative perturbation on the unit vectors,
negligible for the head.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np

from prices.enrich import config

STORE_DIR = config.PRODUCTS_INPUT_PARQUET.parent / "_embed_store"
N_BUCKETS = 256


def bucket_of(name: str) -> int:
    h = hashlib.sha1(str(name).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % N_BUCKETS


def _bucket_path(tag: str, b: int) -> Path:
    return STORE_DIR / tag / f"bucket_{b:03d}.npz"


def _load_bucket(tag: str, b: int) -> dict[str, np.ndarray]:
    p = _bucket_path(tag, b)
    if not p.exists():
        return {}
    with np.load(p, allow_pickle=False) as z:
        keys, mat = z["keys"], z["mat"]
    return {str(k): mat[i] for i, k in enumerate(keys)}


def _save_bucket(tag: str, b: int, store: dict[str, np.ndarray]) -> None:
    p = _bucket_path(tag, b)
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = list(store.keys())
    mat = (
        np.vstack([store[k] for k in keys]) if keys else np.empty((0, 0), np.float16)
    ).astype(np.float16)
    tmp = p.with_suffix(".npz.tmp")
    with open(tmp, "wb") as f:  # file handle => numpy won't append ".npz"
        np.savez(f, keys=np.array(keys), mat=mat)
    tmp.replace(p)


def buckets_for(names) -> dict[int, list[str]]:
    """Map each unique name (order-preserved) to its bucket."""
    out: dict[int, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for n in names:
        n = str(n)
        if n in seen:
            continue
        seen.add(n)
        out[bucket_of(n)].append(n)
    return dict(out)


def missing(tag: str, bucket_names: dict[int, list[str]]) -> dict[int, list[str]]:
    """Per bucket, the names not yet embedded for this block."""
    out: dict[int, list[str]] = {}
    for b, names in bucket_names.items():
        have = _load_bucket(tag, b)
        miss = [n for n in names if n not in have]
        if miss:
            out[b] = miss
    return out


def append(tag: str, b: int, names, vecs: np.ndarray) -> None:
    store = _load_bucket(tag, b)
    for n, v in zip(names, vecs):
        store[str(n)] = np.asarray(v, dtype=np.float16)
    _save_bucket(tag, b, store)


def gather(tag: str, b: int, names) -> np.ndarray:
    """(len(names), dim) fp32 matrix for names in one bucket (all must be present)."""
    store = _load_bucket(tag, b)
    return np.vstack([store[str(n)] for n in names]).astype(np.float32)
