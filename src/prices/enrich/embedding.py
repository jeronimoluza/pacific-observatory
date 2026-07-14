"""Qwen3-Embedding of raw product names for the (embedding → head) classifier.

The head classifies COICOP over L2-normalized Qwen3-Embedding vectors of the
*raw* product name (normalization/canonicalization hurts — feed raw text). Each
name is prefixed with an instruction prompt, encoded fp16, L2-normalized, and
cached on disk keyed by sha256(model || prompt || name) so repeated runs and the
gold/corpus overlap never re-embed.

The model (`sentence-transformers`) is an optional heavy dependency loaded lazily
on the first cache miss; a fully-cached call never imports it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from prices.enrich import config

_MODEL = None


def _load_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(
            config.CLASSIFIER_EMBED_MODEL,
            trust_remote_code=True,
            model_kwargs={"torch_dtype": "float16"},
        )
    return _MODEL


def _key(name: str) -> str:
    h = hashlib.sha256()
    h.update(config.CLASSIFIER_EMBED_MODEL.encode("utf-8"))
    h.update(b"\x00")
    h.update(config.CLASSIFIER_EMBED_PROMPT.encode("utf-8"))
    h.update(b"\x00")
    h.update(name.encode("utf-8"))
    return h.hexdigest()


def _cache_path() -> Path:
    return config.CLASSIFIER_EMBED_CACHE_DIR / "vectors.npz"


def _load_cache() -> dict[str, np.ndarray]:
    p = _cache_path()
    if not p.exists():
        return {}
    with np.load(p, allow_pickle=False) as z:
        keys = z["keys"]
        mat = z["mat"]
    return {str(k): mat[i] for i, k in enumerate(keys)}


def _save_cache(cache: dict[str, np.ndarray]) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = list(cache.keys())
    mat = np.vstack([cache[k] for k in keys]) if keys else np.empty((0, 0), np.float32)
    tmp = p.with_suffix(".npz.tmp")
    with open(tmp, "wb") as f:  # file handle => numpy won't append ".npz"
        np.savez(f, keys=np.array(keys), mat=mat)
    tmp.replace(p)


def embed_names(
    names: Sequence[str], use_cache: bool = True, batch_size: Optional[int] = None
) -> np.ndarray:
    """Return an (N, dim) float32 L2-normalized embedding matrix, row-aligned to
    `names`. Cache hits skip the model; only misses are encoded and persisted."""
    names = [str(n) for n in names]
    if not names:
        return np.empty((0, 0), np.float32)

    cache = _load_cache() if use_cache else {}
    keys = [_key(n) for n in names]
    missing = sorted({k: n for k, n in zip(keys, names) if k not in cache}.items())

    if missing:
        miss_keys = [k for k, _ in missing]
        miss_names = [n for _, n in missing]
        model = _load_model()
        prompt = config.CLASSIFIER_EMBED_PROMPT
        vecs = model.encode(
            [prompt + n for n in miss_names],
            batch_size=batch_size or config.CLASSIFIER_EMBED_BATCH,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype(np.float32)
        for k, v in zip(miss_keys, vecs):
            cache[k] = v
        if use_cache:
            _save_cache(cache)

    return np.vstack([cache[k] for k in keys])
