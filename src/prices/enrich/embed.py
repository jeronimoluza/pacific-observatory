"""Tier (b) text embedding — gemini-embedding-001 with optional e5 fallback.

Gemini is the default backend. The e5-base path requires sentence-transformers
(optional dep) and is only exercised when `EMBED_BACKEND="e5"` or when callers
explicitly request it. Both paths enforce passage/query prefix discipline:
callers MUST pass already-prefixed strings (the index/query module handles this).

Embeddings are cached on disk keyed by sha256(prefixed_text || backend || dim).
Cache invalidation is implicit — a different prefix yields a different hash.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import time
from typing import Iterable, Literal

import numpy as np

from prices.enrich import config


_GEMINI_RPM_DELAY = 60.0 / max(config.EMBED_RPM, 1)
_GEMINI_BATCH = 100
_E5_MODEL = None  # lazy singleton

# Memoized cache singleton. _load_cache populates it on first call and reuses
# the same dict thereafter; embed_texts mutates it in place when new misses
# are computed. Without this, every embed_texts call rebuilt the 200k-entry
# dict from NPZ (~2.5s) and writing it back per-miss (~5-10s), which made
# cascade essentially unusable at scale.
_CACHE_SINGLETON: dict[str, list[float]] | None = None
_CACHE_DIRTY = False
_CACHE_SAVE_INTERVAL_S = 300.0
_CACHE_LAST_SAVE_T: float = 0.0


def _cache_key(text: str, backend: str, dim: int) -> str:
    h = hashlib.sha256()
    h.update(backend.encode())
    h.update(b"|")
    if backend == "e5":
        h.update(config.E5_MODEL_PATH.encode())
        h.update(b"|")
    h.update(str(dim).encode())
    h.update(b"|")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _load_cache() -> dict[str, list[float]]:
    """Memoized: rebuild the dict from NPZ exactly once per process, return
    the same dict on every subsequent call. Callers mutate it in place when
    they compute new embeddings."""
    global _CACHE_SINGLETON
    if _CACHE_SINGLETON is not None:
        return _CACHE_SINGLETON
    p = config.EMBED_CACHE_PATH
    if p.exists():
        try:
            with np.load(p, allow_pickle=False) as d:
                keys = d["keys"]
                vecs = d["vecs"]
            _CACHE_SINGLETON = {str(k): vecs[i] for i, k in enumerate(keys)}
            return _CACHE_SINGLETON
        except Exception:
            _CACHE_SINGLETON = {}
            return _CACHE_SINGLETON
    # One-time migration from the legacy JSON cache.
    legacy = p.with_suffix(".json")
    if legacy.exists():
        try:
            _CACHE_SINGLETON = json.loads(legacy.read_text())
            return _CACHE_SINGLETON
        except Exception:
            _CACHE_SINGLETON = {}
            return _CACHE_SINGLETON
    _CACHE_SINGLETON = {}
    return _CACHE_SINGLETON


def _save_cache(cache: dict[str, list[float]], force: bool = False) -> None:
    """Throttled: full NPZ rewrite costs ~5-10s at 200k+ entries, so we
    coalesce per-miss saves into a single write every _CACHE_SAVE_INTERVAL_S
    (default 5 min). atexit hook flushes any pending writes on shutdown.
    Pass force=True to bypass the throttle (e.g. at end of a batch job)."""
    global _CACHE_DIRTY, _CACHE_LAST_SAVE_T
    _CACHE_DIRTY = True
    now = time.monotonic()
    if not force and (now - _CACHE_LAST_SAVE_T) < _CACHE_SAVE_INTERVAL_S:
        return
    p = config.EMBED_CACHE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    if not cache:
        _CACHE_LAST_SAVE_T = now
        _CACHE_DIRTY = False
        return
    keys = np.array(list(cache.keys()))
    try:
        vecs = np.array(list(cache.values()), dtype=np.float32)
    except (ValueError, TypeError):
        # Mixed-dim cache (e.g. dim config changed mid-run) — skip the write
        # rather than clobber with a ragged array.
        return
    np.savez(p, keys=keys, vecs=vecs)
    _CACHE_LAST_SAVE_T = now
    _CACHE_DIRTY = False


def _flush_cache_on_exit() -> None:
    if _CACHE_SINGLETON is not None and _CACHE_DIRTY:
        try:
            _save_cache(_CACHE_SINGLETON, force=True)
        except Exception:
            pass


atexit.register(_flush_cache_on_exit)


_RETRY_DELAY_RE = None  # parsed from google.api_core errors directly


def _embed_gemini(texts: list[str], dim: int) -> list[list[float]]:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY / GEMINI_API_KEY must be set for gemini embedding backend"
        )
    import google.generativeai as genai
    from google.api_core import exceptions as gax_exceptions

    genai.configure(api_key=api_key)
    out: list[list[float]] = []
    i = 0
    while i < len(texts):
        batch = texts[i : i + _GEMINI_BATCH]
        try:
            resp = genai.embed_content(
                model=config.EMBED_MODEL_GEMINI,
                content=batch,
                task_type="SEMANTIC_SIMILARITY",
            )
        except gax_exceptions.ResourceExhausted as e:
            # 429: honour retry_delay from the violation; fall back to 30s.
            delay = 30.0
            try:
                if getattr(e, "_details", None):
                    for d in e._details:
                        rd = getattr(d, "retry_delay", None)
                        if rd is not None and getattr(rd, "seconds", 0):
                            delay = float(rd.seconds) + 1.0
                            break
            except Exception:
                pass
            time.sleep(delay)
            continue
        vecs = resp["embedding"]
        if isinstance(vecs[0], (int, float)):
            vecs = [vecs]
        for v in vecs:
            arr = np.asarray(v, dtype=np.float32)[:dim]
            out.append(arr.tolist())
        i += _GEMINI_BATCH
        if i < len(texts):
            time.sleep(_GEMINI_RPM_DELAY)
    return out


def _embed_e5(texts: list[str], dim: int) -> list[list[float]]:
    global _E5_MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            "EMBED_BACKEND='e5' requires sentence-transformers (poetry add sentence-transformers)"
        ) from e
    if _E5_MODEL is None:
        _E5_MODEL = SentenceTransformer(config.E5_MODEL_PATH)
    arr = _E5_MODEL.encode(texts, batch_size=32, normalize_embeddings=True)
    # Cast to python floats so the JSON cache layer can serialize them.
    return [[float(x) for x in v[:dim]] for v in arr.astype(np.float32)]


def embed_texts(
    texts: Iterable[str],
    backend: Literal["gemini", "e5"] | None = None,
    dim: int | None = None,
    use_cache: bool = True,
) -> np.ndarray:
    """Return an (n, dim) float32 array. Caller pre-prefixes with `passage:`
    or `query:` (this function is prefix-agnostic — it just hashes & embeds)."""
    texts = list(texts)
    backend = backend or config.EMBED_BACKEND
    dim = dim or config.EMBED_DIM
    if not texts:
        return np.zeros((0, dim), dtype=np.float32)

    cache = _load_cache() if use_cache else {}
    keys = [_cache_key(t, backend, dim) for t in texts]
    out: list[list[float] | None] = [cache.get(k) for k in keys]
    miss_idx = [i for i, v in enumerate(out) if v is None]
    if miss_idx:
        miss_texts = [texts[i] for i in miss_idx]
        if backend == "gemini":
            fresh = _embed_gemini(miss_texts, dim)
        elif backend == "e5":
            fresh = _embed_e5(miss_texts, dim)
        else:
            raise ValueError(f"unknown embed backend: {backend}")
        for i, v in zip(miss_idx, fresh):
            out[i] = v
            cache[keys[i]] = v
        if use_cache:
            _save_cache(cache)

    return np.asarray(out, dtype=np.float32)
