"""Embed the full name universe on a CUDA GPU, all four blocks.

CUDA port of jero_embed.py. Same store layout, same disk-derived resume, same
instruction prefix and per-block L2, but every block runs through
sentence-transformers on the GPU instead of the MLX subprocess. No half/bucket
restriction: this walks all 256 buckets.

    QWEN_EMBED_BATCH=512 PYTHONPATH=src python src/prices/enrich/gpu/gpu_embed.py --status
    QWEN_EMBED_BATCH=512 PYTHONPATH=src python src/prices/enrich/gpu/gpu_embed.py --model 4b
    ... --bench 20000            # E0: throughput / $-per-million calibration
    ... --parity 10000 --model 4b  # E1: cosine agreement vs the MLX vectors on disk

The 8B block writes tag `8b_bf16`, NOT `8b_q8`. The existing 8b_q8 vectors came
from a locally-quantized int8 MLX build; bf16 on GPU is a different weight set
and therefore a different vector space. Keeping the tags separate is what stops
the two from silently mixing in one bucket file.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config, embedding
from prices.enrich.classifier import embed_store

SPLIT = Path("data/prices/_enrich/transfer/embed_names_split_20260819.parquet")
CHECKPOINT_EVERY = int(os.environ.get("GPU_CHECKPOINT_EVERY", "20000"))

_DTYPE = os.environ.get("EMBED_DTYPE", "bfloat16")
_MK = {"torch_dtype": _DTYPE}

# Block specs mirror config.CLASSIFIER_EMBED_PRESETS, with backend forced to
# "st" (no MLX on CUDA) and the 8B pointed at the upstream bf16 weights.
GPU_BLOCKS: dict[str, dict] = {
    "0p6b": {
        "tag": "0p6b",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "seq": 48,
        "model_kwargs": _MK,
    },
    "4b": {
        "tag": "4b",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-4B",
        "seq": 176,
        "model_kwargs": _MK,
    },
    "8b_bf16": {
        "tag": "8b_bf16",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-8B",
        "seq": 176,
        "model_kwargs": _MK,
    },
    "arctic_l_v2": {
        "tag": "arctic_l_v2",
        "backend": "st",
        "model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "seq": 48,
        "prompt": "",
        "model_kwargs": _MK,
    },
}

_stop = False


def _on_sigint(signum, frame):
    global _stop
    if _stop:
        print("\n[second interrupt] exiting now", flush=True)
        sys.exit(130)
    _stop = True
    print("\n[interrupt] finishing current chunk, then stopping...", flush=True)


def bucket_keys(tag: str, b: int) -> set[str]:
    """Names already stored for (tag, bucket) — reads `keys` only, never `mat`."""
    p = embed_store.STORE_DIR / tag / f"bucket_{b:03d}.npz"
    if not p.exists():
        return set()
    try:
        with np.load(p, allow_pickle=False) as z:
            return {str(k) for k in z["keys"]}
    except Exception:
        return set()


def load_names() -> dict[int, list[str]]:
    df = pd.read_parquet(SPLIT, columns=["product_name_original", "bucket"])
    out: dict[int, list[str]] = {}
    for b, g in df.groupby("bucket"):
        out[int(b)] = list(dict.fromkeys(g["product_name_original"].astype(str)))
    return out


def block_for(tag: str) -> dict:
    if tag not in GPU_BLOCKS:
        sys.exit(f"unknown model tag {tag} (have {', '.join(GPU_BLOCKS)})")
    return GPU_BLOCKS[tag]


def encode(blk: dict, names: list[str]) -> np.ndarray:
    return embedding.encode_st_block(blk, names)


def report(by_bucket: dict[int, list[str]]) -> None:
    total = sum(len(v) for v in by_bucket.values())
    print(f"{'model':<12}{'stored':>12}{'missing':>12}{'pct':>8}")
    for tag in GPU_BLOCKS:
        have = sum(
            len(set(names) & bucket_keys(tag, b)) for b, names in by_bucket.items()
        )
        print(f"{tag:<12}{have:>12,}{total - have:>12,}{100 * have / total:>7.1f}%")
    print(f"{'TOTAL':<12}{total:>12,}")


def single_run_lock(tag: str) -> Path:
    lock = embed_store.STORE_DIR / f".lock_{tag}"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
            sys.exit(f"Another '{tag}' run is already in progress (pid {pid}).")
        except (ValueError, ProcessLookupError):
            pass
    lock.write_text(str(os.getpid()))
    return lock


def run(tag: str) -> None:
    by_bucket = load_names()
    blk = block_for(tag)
    todo = {}
    for b in sorted(by_bucket):
        have = bucket_keys(tag, b)
        miss = [n for n in by_bucket[b] if n not in have]
        if miss:
            todo[b] = miss
    left = sum(len(v) for v in todo.values())
    if not left:
        print(f"[{tag}] COMPLETE - nothing to do")
        return
    print(f"[{tag}] {left:,} names missing across {len(todo)} buckets", flush=True)

    (embed_store.STORE_DIR / tag).mkdir(parents=True, exist_ok=True)
    lock = single_run_lock(tag)
    signal.signal(signal.SIGINT, _on_sigint)
    done, t_start = 0, time.monotonic()
    try:
        for b in sorted(todo):
            names = todo[b]
            for i in range(0, len(names), CHECKPOINT_EVERY):
                if _stop:
                    raise KeyboardInterrupt
                chunk = names[i : i + CHECKPOINT_EVERY]
                t0 = time.monotonic()
                vecs = encode(blk, chunk)
                embed_store.append(tag, b, chunk, vecs)
                done += len(chunk)
                dt = time.monotonic() - t0
                rate = done / max(time.monotonic() - t_start, 1e-9)
                print(
                    f"[{tag}] bucket {b:03d} +{len(chunk)} in {dt:.0f}s "
                    f"({len(chunk) / dt:.0f}/s) | {done:,}/{left:,} "
                    f"| ETA {(left - done) / rate / 3600:.2f}h",
                    flush=True,
                )
    except KeyboardInterrupt:
        print(
            f"[{tag}] stopped cleanly at {done:,}/{left:,}. Re-run to resume.",
            flush=True,
        )
    finally:
        embedding.free_st()
        lock.unlink(missing_ok=True)


def bench(n: int, hourly: float) -> None:
    """E0: measure names/s and $/million for every block on this GPU."""
    by_bucket = load_names()
    pool = [x for b in sorted(by_bucket) for x in by_bucket[b]][: n * 2]
    print(
        f"batch={config.CLASSIFIER_EMBED_BATCH} dtype={_DTYPE} n={n:,} "
        f"hourly=${hourly:.2f}\n"
    )
    print(
        f"{'model':<12}{'warm s':>9}{'names/s':>10}{'h/5.41M':>10}{'$/M':>9}{'$/5.41M':>10}"
    )
    for tag, blk in GPU_BLOCKS.items():
        try:
            encode(blk, pool[:16])  # warm weights + kernels
            t0 = time.monotonic()
            encode(blk, pool[:n])
            dt = time.monotonic() - t0
            rate = n / dt
            hours = 5_414_606 / rate / 3600
            print(
                f"{tag:<12}{dt:>9.1f}{rate:>10.0f}{hours:>10.2f}"
                f"{hourly / (rate * 3600 / 1e6):>9.2f}{hours * hourly:>10.2f}"
            )
        except Exception as e:
            print(f"{tag:<12}  FAILED: {type(e).__name__}: {str(e)[:80]}")
        finally:
            embedding.free_st()


def parity(tag: str, n: int) -> None:
    """E1: cosine agreement between GPU vectors and the MLX vectors on disk."""
    blk = block_for(tag)
    src = os.environ.get("PARITY_SRC_TAG", "8b_q8" if tag == "8b_bf16" else tag)
    names, ref = [], []
    for b in range(256):
        p = embed_store.STORE_DIR / src / f"bucket_{b:03d}.npz"
        if not p.exists():
            continue
        with np.load(p, allow_pickle=False) as z:
            k, m = z["keys"], z["mat"]
        take = min(len(k), max(1, n // 64))
        names += [str(x) for x in k[:take]]
        ref.append(m[:take].astype(np.float32))
        if len(names) >= n:
            break
    names, ref = names[:n], np.vstack(ref)[:n]
    print(f"[parity] {tag} (gpu) vs {src} (disk) on {len(names):,} names", flush=True)

    gpu = encode(blk, names)
    ref = ref / (np.linalg.norm(ref, axis=1, keepdims=True) + 1e-9)
    cos = np.sum(gpu * ref, axis=1)
    print(
        f"  mean {cos.mean():.6f}  p50 {np.percentile(cos, 50):.6f}  "
        f"p01 {np.percentile(cos, 1):.6f}  min {cos.min():.6f}"
    )
    for thr in (0.9999, 0.999, 0.99, 0.95):
        print(f"  frac below {thr:<7}: {(cos < thr).mean():.4%}")
    print(
        "  VERDICT:",
        "reusable — mixing is safe"
        if np.percentile(cos, 1) >= 0.999
        else "NOT reusable — re-embed this tier under its own tag",
    )
    embedding.free_st()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(GPU_BLOCKS))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--bench", type=int, metavar="N")
    ap.add_argument("--parity", type=int, metavar="N")
    ap.add_argument("--hourly", type=float, default=2.99)
    a = ap.parse_args()
    if a.status:
        return report(load_names())
    if a.bench:
        return bench(a.bench, a.hourly)
    if a.parity:
        if not a.model:
            ap.error("--parity needs --model")
        return parity(a.model, a.parity)
    if not a.model:
        ap.error(
            f"pass --model {{{','.join(GPU_BLOCKS)}}}, --status, --bench N, or --parity N"
        )
    run(a.model)


if __name__ == "__main__":
    main()
