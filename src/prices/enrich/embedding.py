"""Ensemble Qwen3-Embedding of raw product names for the (embedding → head) head.

The head classifies COICOP over the CONCATENATION of three frozen Qwen3-Embedding
encoders — 0.6B + 4B + 8B(q8) — of the *raw* product name (normalization hurts —
feed raw text). Each block is L2-normalized independently, then the blocks are
joined with NO global renorm (per-block L2 keeps any one encoder from dominating
by magnitude; this concat is the biggest cov@98 lever, ~47% → ~63% on div-01).

Backends are mixed per block, matching the recipe that produced that number:

  - 0.6B → sentence-transformers, IN-PROCESS, seq-len 48 (the recipe used ST; mlx
    loading of the raw 0.6B is flaky).
  - 4B / 8B-q8 → `mlx_embeddings` in the sibling `.venv_mlx`, seq-len 512, reached
    by a subprocess to `embedding_mlx.py` (the 8B only fits 16GB as an mlx q8).

Per-block vectors are cached on disk keyed by name (one `.npz` per block) so the
gold/corpus overlap and repeat runs never re-embed; a fully-cached call touches
neither the ST model nor the mlx subprocess.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

import numpy as np

from prices.enrich import config

_RUNNER = Path(__file__).resolve().parent / "embedding_mlx.py"
_ST_MODELS: dict[str, object] = {}


def _block_cache_path(tag: str) -> Path:
    return config.CLASSIFIER_EMBED_CACHE_DIR / f"block_{tag}.npz"


def _load_block_cache(tag: str) -> dict[str, np.ndarray]:
    p = _block_cache_path(tag)
    if not p.exists():
        return {}
    with np.load(p, allow_pickle=False) as z:
        keys, mat = z["keys"], z["mat"]
    return {str(k): mat[i] for i, k in enumerate(keys)}


def _save_block_cache(tag: str, cache: dict[str, np.ndarray]) -> None:
    p = _block_cache_path(tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = list(cache.keys())
    mat = np.vstack([cache[k] for k in keys]) if keys else np.empty((0, 0), np.float32)
    tmp = p.with_suffix(".npz.tmp")
    with open(tmp, "wb") as f:  # file handle => numpy won't append ".npz"
        np.savez(f, keys=np.array(keys), mat=mat)
    tmp.replace(p)


def _encode_st(block: dict, names: Sequence[str]) -> np.ndarray:
    """In-process sentence-transformers encode (used for the 0.6B block)."""
    model_id = block["model"]
    model = _ST_MODELS.get(model_id)
    if model is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            model_id,
            trust_remote_code=True,
            config_kwargs=block.get("config_kwargs") or {},
            model_kwargs=block.get("model_kwargs") or {},
        )
        _ST_MODELS[model_id] = model
    model.max_seq_length = int(block["seq"])
    prompt = block.get("prompt", config.CLASSIFIER_EMBED_PROMPT)
    return model.encode(
        [prompt + n for n in names],
        batch_size=config.CLASSIFIER_EMBED_BATCH,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype(np.float32)


def _encode_mlx(block: dict, names: Sequence[str]) -> np.ndarray:
    """Subprocess encode via `mlx_embeddings` in `.venv_mlx` (4B / 8B blocks)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "vecs.npz"
        payload = Path(td) / "payload.json"
        payload.write_text(
            json.dumps(
                {
                    "model": block["model"],
                    "prompt": config.CLASSIFIER_EMBED_PROMPT,
                    "names": list(names),
                    "out": str(out),
                    "chunk": config.CLASSIFIER_EMBED_BATCH,
                    "seq": int(block["seq"]),
                }
            )
        )
        proc = subprocess.run(
            [str(config.MLX_VENV_PYTHON), str(_RUNNER), str(payload)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"mlx embed subprocess failed for {block['model']} "
                f"(python={config.MLX_VENV_PYTHON}):\n{proc.stderr[-2000:]}"
            )
        with np.load(out, allow_pickle=False) as z:
            keys, mat = z["keys"], z["mat"]
    by_name = {str(k): mat[i] for i, k in enumerate(keys)}
    return np.vstack([by_name[n] for n in names]).astype(np.float32)


def _l2(mat: np.ndarray) -> np.ndarray:
    return (mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)).astype(
        np.float32
    )


def encode_st_block(block: dict, names: Sequence[str]) -> np.ndarray:
    """Public per-row-L2 0.6B encode for the block-outer driver."""
    return _l2(_encode_st(block, names))


def free_st() -> None:
    """Release the cached sentence-transformers model + its MPS allocations.

    The block-outer driver calls this after the 0.6B block so its ~2.5 GB does
    not sit resident (on unified memory) while the 8B mlx worker holds 7.5 GB.
    """
    _ST_MODELS.clear()
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        # On CUDA the caching allocator keeps the freed blocks, so a pod running
        # several blocks in one process would still be holding 8B's ~16 GB when
        # 4B loads. Dropping the dict is not enough there.
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    import gc

    gc.collect()


class MlxWorker:
    """A long-lived `.venv_mlx` subprocess that loads one model once and embeds
    successive chunks over stdin (see `embedding_mlx.py --serve`). Used by the
    full-corpus driver so the 8B/4B weights load a single time per run instead
    of once per chunk."""

    def __init__(self, model_id: str):
        self.proc = subprocess.Popen(
            [str(config.MLX_VENV_PYTHON), str(_RUNNER), "--serve", model_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._await("READY")

    def _await(self, token: str) -> None:
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                raise RuntimeError(f"mlx worker exited before '{token}'")
            if line.strip() == token:
                return

    def encode(self, block: dict, names: Sequence[str]) -> np.ndarray:
        """Embed `names` with this worker's model; returns an (N, dim) per-row
        L2-normalized float32 matrix row-aligned to `names`."""
        names = [str(n) for n in names]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "vecs.npz"
            payload = Path(td) / "payload.json"
            payload.write_text(
                json.dumps(
                    {
                        "prompt": config.CLASSIFIER_EMBED_PROMPT,
                        "names": names,
                        "out": str(out),
                        "chunk": config.CLASSIFIER_EMBED_BATCH,
                        "seq": int(block["seq"]),
                    }
                )
            )
            self.proc.stdin.write(str(payload) + "\n")
            self.proc.stdin.flush()
            self._await("OK")
            with np.load(out, allow_pickle=False) as z:
                keys, mat = z["keys"], z["mat"]
        by_name = {str(k): mat[i] for i, k in enumerate(keys)}
        return _l2(np.vstack([by_name[n] for n in names]).astype(np.float32))

    def close(self) -> None:
        try:
            self.proc.stdin.write("__STOP__\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=60)
        except Exception:
            self.proc.kill()


def _encode_block(block: dict, names: Sequence[str]) -> np.ndarray:
    """Embed `names` with one block's encoder. Returns an (N, dim) per-row
    L2-normalized float32 matrix, row-aligned to `names`."""
    if block["backend"] == "st":
        return _encode_st(block, names)
    return _encode_mlx(block, names)


def _gather_from_store(block: dict, names: list[str]) -> np.ndarray:
    """Read one block's vectors out of the durable name-keyed store.

    Rows are copied into a preallocated output rather than collected as the views
    `embed_store` hands back: a view keeps its whole bucket matrix alive, so
    holding one per name pins the entire block on the heap (42 GB for the 8B).
    """
    from prices.enrich.classifier import embed_store

    tag = block["tag"]
    uniq = list(dict.fromkeys(names))
    pos = {n: i for i, n in enumerate(uniq)}
    out = np.zeros((len(uniq), int(block["dim"])), np.float32)
    seen = np.zeros(len(uniq), bool)
    for b, bucket_names in embed_store.buckets_for(uniq).items():
        store = embed_store._load_bucket(tag, b)
        for n in bucket_names:
            v = store.get(n)
            if v is not None:
                out[pos[n]] = v
                seen[pos[n]] = True
        del store
    if not seen.all():
        miss = [uniq[i] for i in np.flatnonzero(~seen)[:5]]
        raise KeyError(
            f"{int((~seen).sum())} name(s) not in embed store block {tag!r}, "
            f"e.g. {miss} — embed them first, or drop them with `covered_mask`"
        )
    return out[[pos[n] for n in names]]


def covered_mask(names: Sequence[str]) -> np.ndarray:
    """Which names the store already holds for EVERY configured block.

    The GPU store does not cover gold completely (~0.3% of names were never
    embedded). Callers restrict to this mask rather than back-filling from another
    backend: mixing two vector spaces inside one matrix is silently harmful.
    """
    from prices.enrich.classifier import embed_store

    names = [str(n) for n in names]
    tags = [
        b["tag"]
        for b in config.CLASSIFIER_EMBED_ENSEMBLE
        if b.get("backend") == "store"
    ]
    if not tags:
        return np.ones(len(names), bool)
    have: set[str] | None = None
    bmap = embed_store.buckets_for(names)
    for tag in tags:
        seen: set[str] = set()
        for b, bucket_names in bmap.items():
            path = embed_store._bucket_path(tag, b)
            if not path.exists():
                continue
            with np.load(path, allow_pickle=False) as z:
                seen |= set(embed_store.decode_keys(z)) & set(bucket_names)
        have = seen if have is None else (have & seen)
    return np.array([n in have for n in names], bool)


def finalize_block(block: dict, mat: np.ndarray) -> np.ndarray:
    """Per-row L2 then the block's weight — the step between a raw block matrix
    and its columns of the ensemble.

    Public because the full-corpus driver reads vectors straight out of the store
    rather than through `embed_names`. Skipping it there would feed UNWEIGHTED
    columns to a head fitted on weighted ones, which produces confident nonsense
    rather than an error.
    """
    mat = np.asarray(mat, np.float32)
    mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    w = float(block.get("weight", 1.0))
    return mat if w == 1.0 else (mat * np.float32(w))


def _embed_one_block(block: dict, names: list[str], use_cache: bool) -> np.ndarray:
    if block.get("backend") == "store":
        block_mat = _gather_from_store(block, names)
    else:
        tag = block["tag"]
        cache = _load_block_cache(tag) if use_cache else {}
        missing = list(dict.fromkeys(n for n in names if n not in cache))
        if missing:
            vecs = _encode_block(block, missing)
            for n, v in zip(missing, vecs):
                cache[n] = v
            if use_cache:
                _save_block_cache(tag, cache)
        block_mat = np.vstack([cache[n] for n in names]).astype(np.float32)
    # per-block L2 (idempotent — the backend already unit-normalizes; defensive)
    return finalize_block(block, block_mat)


def embed_names(names: Sequence[str], use_cache: bool = True) -> np.ndarray:
    """Return the (N, sum-of-block-dims) float32 ensemble matrix, row-aligned to
    `names`: each configured encoder's per-row L2 vector scaled by its block
    weight, concatenated in config order with no global renorm."""
    names = [str(n) for n in names]
    if not names:
        return np.empty((0, 0), np.float32)
    blocks = [
        _embed_one_block(block, names, use_cache)
        for block in config.CLASSIFIER_EMBED_ENSEMBLE
    ]
    return np.hstack(blocks).astype(np.float32)
