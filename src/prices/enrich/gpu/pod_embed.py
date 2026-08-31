"""Embed a fixed name list on a CUDA pod, one flat npz per block.

Writes `<out>/block_<tag>.npz` (keys `<U255`, mat float16) using the same
`embedding.encode_st_block` path as production, so the prompt, seq-len and
per-block L2 match the Mac exactly and only the backend differs. Tags carry a
`_gpu` suffix where a Mac cache of the same encoder already exists, so the two
never collide when the npz files are copied back.

Chunked and resumable: each chunk appends to `block_<tag>.part.npz`, so a kill
mid-model resumes from the last chunk instead of restarting the model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prices.enrich import config, embedding  # noqa: E402

_MK = {"torch_dtype": "bfloat16"}

BLOCKS: dict[str, dict] = {
    "0p6b_gpu": {
        "tag": "0p6b_gpu",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "seq": 48,
        "batch": 512,
        "model_kwargs": _MK,
    },
    "arctic_gpu": {
        "tag": "arctic_gpu",
        "model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "seq": 48,
        "batch": 512,
        "prompt": "",
        "model_kwargs": _MK,
    },
    "4b_gpu": {
        "tag": "4b_gpu",
        "model": "Qwen/Qwen3-Embedding-4B",
        "seq": 176,
        "batch": 256,
        "model_kwargs": _MK,
    },
    "8b_bf16": {
        "tag": "8b_bf16",
        "model": "Qwen/Qwen3-Embedding-8B",
        "seq": 176,
        "batch": 128,
        "model_kwargs": _MK,
    },
}


def _load_part(path: Path) -> tuple[list[str], list[np.ndarray]]:
    if not path.exists():
        return [], []
    with np.load(path, allow_pickle=False) as z:
        return [str(k) for k in z["keys"]], list(z["mat"])


def _save(path: Path, keys: list[str], mat: list[np.ndarray]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        np.savez(
            f,
            keys=np.array(keys),
            mat=np.vstack(mat).astype(np.float16)
            if mat
            else np.empty((0, 0), np.float16),
        )
    tmp.replace(path)


def run_block(key: str, names: list[str], out_dir: Path, chunk: int) -> dict:
    blk = BLOCKS[key]
    tag = blk["tag"]
    final = out_dir / f"block_{tag}.npz"
    if final.exists():
        print(f"{tag}: already complete, skipping", flush=True)
        return {"tag": tag, "skipped": True}

    part = out_dir / f"block_{tag}.part.npz"
    done_keys, done_mat = _load_part(part)
    done = set(done_keys)
    todo = [n for n in names if n not in done]
    print(
        f"{tag}: {len(done)} cached, {len(todo)} to encode "
        f"(batch={blk['batch']}, seq={blk['seq']})",
        flush=True,
    )

    config.CLASSIFIER_EMBED_BATCH = int(blk["batch"])
    t_load = time.time()
    encoded = 0
    elapsed = 0.0
    for i in range(0, len(todo), chunk):
        part_names = todo[i : i + chunk]
        t0 = time.time()
        vecs = embedding.encode_st_block(blk, part_names)
        dt = time.time() - t0
        if encoded == 0:
            load_s = t0 - t_load
            print(f"{tag}: model ready in {load_s:.1f}s", flush=True)
        elapsed += dt
        encoded += len(part_names)
        done_keys.extend(part_names)
        done_mat.extend(list(vecs))
        _save(part, done_keys, done_mat)
        print(
            f"{tag}: {encoded}/{len(todo)} | {len(part_names) / dt:.1f} names/s "
            f"| chunk {dt:.1f}s",
            flush=True,
        )

    _save(final, done_keys, done_mat)
    part.unlink(missing_ok=True)
    rate = encoded / elapsed if elapsed else float("nan")
    print(f"{tag}: DONE {len(done_keys)} rows | {rate:.1f} names/s", flush=True)
    return {
        "tag": tag,
        "rows": len(done_keys),
        "encoded": encoded,
        "encode_s": round(elapsed, 1),
        "names_per_s": round(rate, 1),
        "dim": int(np.vstack(done_mat[:1]).shape[1]) if done_mat else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True)
    ap.add_argument("--col", default="product_name")
    ap.add_argument("--out", default="/workspace/out")
    ap.add_argument("--models", default="0p6b_gpu,arctic_gpu,4b_gpu,8b_bf16")
    ap.add_argument("--chunk", type=int, default=5000)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    df = pd.read_parquet(a.names)
    names = df[a.col].astype(str).drop_duplicates().tolist()
    if a.limit:
        names = names[: a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(names)} unique names -> {out}", flush=True)

    stats = []
    for key in a.models.split(","):
        key = key.strip()
        if key not in BLOCKS:
            raise SystemExit(f"unknown block {key!r}; have {list(BLOCKS)}")
        t0 = time.time()
        s = run_block(key, names, out, a.chunk)
        s["wall_s"] = round(time.time() - t0, 1)
        stats.append(s)
        (out / "timings.json").write_text(json.dumps(stats, indent=1))

    print("\n=== throughput ===", flush=True)
    for s in stats:
        if s.get("skipped"):
            continue
        print(
            f"  {s['tag']:<12} dim={s['dim']:<5} {s['names_per_s']:>8.1f} names/s "
            f"| wall {s['wall_s']}s",
            flush=True,
        )


if __name__ == "__main__":
    main()
