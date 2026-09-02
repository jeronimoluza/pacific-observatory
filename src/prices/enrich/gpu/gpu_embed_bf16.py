"""Embed the full name universe on a CUDA GPU, all four blocks.

CUDA port of jero_embed.py. Same store layout, same disk-derived resume, same
instruction prefix and per-block L2, but every block runs through
sentence-transformers on the GPU instead of the MLX subprocess.

    QWEN_EMBED_BATCH unused here -- each block carries its own batch size.

    PYTHONPATH=src python src/prices/enrich/gpu/gpu_embed.py --status
    PYTHONPATH=src python src/prices/enrich/gpu/gpu_embed.py --bucket-lo 0 --bucket-hi 42
    ... --bench 20000                   # E0: throughput / $-per-million calibration
    ... --parity 10000 --model 4b_bf16  # E1: cosine agreement vs the MLX vectors

EVERY block writes a `_bf16` tag, distinct from the `0p6b`/`4b`/`8b_q8` tags the
Macs wrote. Those came from MLX (4B, 8B int8) or fp32 MPS (0.6B); bf16 on CUDA is
a different arithmetic and therefore a different vector space. Resume is
disk-derived, so reusing a Mac tag here would make the pod skip the ~1.7M names
that tag already holds and append bf16 vectors alongside MLX ones inside the same
bucket -- two spaces in one file, silently. Separate tags are what prevent that.
Run --parity if you want to measure whether a tier is in fact reusable.

Work is partitioned by bucket range. bucket_of(name) is a pure function of the
name, so a name belongs to exactly one bucket and therefore to exactly one pod:
disjoint --bucket-lo/--bucket-hi ranges cover the universe with no name embedded
twice and no coordination between pods.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from prices.enrich import config, embedding
from prices.enrich.classifier import embed_store

UNIVERSE = Path(
    os.environ.get(
        "EMBED_UNIVERSE",
        "data/prices/_enrich/transfer/embed_universe_cc_20260901.parquet",
    )
)
CHECKPOINT_EVERY = int(os.environ.get("GPU_CHECKPOINT_EVERY", "20000"))

_DTYPE = os.environ.get("EMBED_DTYPE", "bfloat16")
_MK = {"torch_dtype": _DTYPE}

# Block specs mirror config.CLASSIFIER_EMBED_PRESETS, with backend forced to
# "st" (no MLX on CUDA) and every tag suffixed _bf16. Ordered most-expensive
# first so the block that dominates wall-clock starts immediately.
GPU_BLOCKS: dict[str, dict] = {
    "8b_bf16": {
        "tag": "8b_bf16",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-8B",
        "seq": 176,
        "batch": 128,
        "model_kwargs": _MK,
    },
    "4b_bf16": {
        "tag": "4b_bf16",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-4B",
        "seq": 176,
        "batch": 256,
        "model_kwargs": _MK,
    },
    "0p6b_bf16": {
        "tag": "0p6b_bf16",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "seq": 48,
        "batch": 512,
        "model_kwargs": _MK,
    },
    "arctic_bf16": {
        "tag": "arctic_bf16",
        "backend": "st",
        "model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "seq": 48,
        "batch": 512,
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
    """Names already stored for (tag, bucket) -- reads keys only, never `mat`."""
    p = embed_store.STORE_DIR / tag / f"bucket_{b:03d}.npz"
    if not p.exists():
        return set()
    try:
        with np.load(p, allow_pickle=False) as z:
            return set(embed_store.decode_keys(z))
    except Exception:
        return set()


def load_names(lo: int, hi: int) -> dict[int, list[str]]:
    """Unique names per bucket for buckets lo..hi inclusive."""
    t = pq.read_table(
        UNIVERSE,
        columns=["product_name_original", "bucket"],
        filters=[("bucket", ">=", lo), ("bucket", "<=", hi)],
    )
    out: dict[int, list[str]] = {}
    for name, b in zip(
        t.column("product_name_original").to_pylist(),
        t.column("bucket").to_pylist(),
    ):
        out.setdefault(int(b), []).append(str(name))
    return {b: list(dict.fromkeys(v)) for b, v in out.items()}


def block_for(tag: str) -> dict:
    if tag not in GPU_BLOCKS:
        sys.exit(f"unknown model tag {tag} (have {', '.join(GPU_BLOCKS)})")
    return GPU_BLOCKS[tag]


def encode(blk: dict, names: list[str]) -> np.ndarray:
    config.CLASSIFIER_EMBED_BATCH = int(blk["batch"])
    return embedding.encode_st_block(blk, names)


def report(by_bucket: dict[int, list[str]], lo: int, hi: int) -> None:
    total = sum(len(v) for v in by_bucket.values())
    print(f"buckets {lo}-{hi}: {total:,} names\n")
    print(f"{'model':<14}{'stored':>12}{'missing':>12}{'pct':>8}")
    for tag in GPU_BLOCKS:
        have = sum(
            len(set(names) & bucket_keys(tag, b)) for b, names in by_bucket.items()
        )
        pct = 100 * have / total if total else 0.0
        print(f"{tag:<14}{have:>12,}{total - have:>12,}{pct:>7.1f}%")


def single_run_lock(tag: str, lo: int, hi: int) -> Path:
    """One lock per (tag, bucket range) so disjoint ranges never serialise."""
    lock = embed_store.STORE_DIR / f".lock_{tag}_{lo:03d}_{hi:03d}"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
            sys.exit(f"Another '{tag}' run on buckets {lo}-{hi} is live (pid {pid}).")
        except (ValueError, ProcessLookupError):
            pass
    lock.write_text(str(os.getpid()))
    return lock


def run(tag: str, by_bucket: dict[int, list[str]], lo: int, hi: int) -> None:
    blk = block_for(tag)
    todo = {}
    for b in sorted(by_bucket):
        have = bucket_keys(tag, b)
        miss = [n for n in by_bucket[b] if n not in have]
        if miss:
            todo[b] = miss
    left = sum(len(v) for v in todo.values())
    if not left:
        print(f"[{tag}] COMPLETE - nothing to do", flush=True)
        return
    print(f"[{tag}] {left:,} names missing across {len(todo)} buckets", flush=True)

    (embed_store.STORE_DIR / tag).mkdir(parents=True, exist_ok=True)
    lock = single_run_lock(tag, lo, hi)
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
        raise
    finally:
        embedding.free_st()
        lock.unlink(missing_ok=True)


def bench(n: int, hourly: float, lo: int, hi: int) -> None:
    """E0: measure names/s and $/million for every block on this GPU."""
    by_bucket = load_names(lo, hi)
    pool = [x for b in sorted(by_bucket) for x in by_bucket[b]][: n * 2]
    total = pq.ParquetFile(UNIVERSE).metadata.num_rows
    print(f"dtype={_DTYPE} n={n:,} hourly=${hourly:.2f} universe={total:,}\n")
    print(
        f"{'model':<14}{'batch':>7}{'warm s':>9}{'names/s':>10}{'hours':>9}{'$/M':>9}{'$':>9}"
    )
    for tag, blk in GPU_BLOCKS.items():
        try:
            encode(blk, pool[:16])  # warm weights + kernels
            t0 = time.monotonic()
            encode(blk, pool[:n])
            dt = time.monotonic() - t0
            rate = n / dt
            hours = total / rate / 3600
            print(
                f"{tag:<14}{blk['batch']:>7}{dt:>9.1f}{rate:>10.0f}{hours:>9.2f}"
                f"{hourly / (rate * 3600 / 1e6):>9.2f}{hours * hourly:>9.2f}"
            )
        except Exception as e:
            print(f"{tag:<14}  FAILED: {type(e).__name__}: {str(e)[:80]}")
        finally:
            embedding.free_st()


def parity(tag: str, n: int) -> None:
    """E1: cosine agreement between GPU vectors and the MLX vectors on disk."""
    blk = block_for(tag)
    default_src = {
        "8b_bf16": "8b_q8",
        "4b_bf16": "4b",
        "0p6b_bf16": "0p6b",
        "arctic_bf16": "arctic_l_v2",
    }[tag]
    src = os.environ.get("PARITY_SRC_TAG", default_src)
    names, ref = [], []
    for b in range(256):
        p = embed_store.STORE_DIR / src / f"bucket_{b:03d}.npz"
        if not p.exists():
            continue
        with np.load(p, allow_pickle=False) as z:
            k, m = embed_store.decode_keys(z), z["mat"]
        take = min(len(k), max(1, n // 64))
        names += k[:take]
        ref.append(m[:take].astype(np.float32))
        if len(names) >= n:
            break
    if not names:
        sys.exit(f"no vectors on disk under tag '{src}' to compare against")
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
        "reusable - mixing is safe"
        if np.percentile(cos, 1) >= 0.999
        else "NOT reusable - re-embed this tier under its own tag",
    )
    embedding.free_st()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="single tag, for --parity")
    ap.add_argument(
        "--models",
        default=",".join(GPU_BLOCKS),
        help="comma-separated tags to run, in order",
    )
    ap.add_argument("--bucket-lo", type=int, default=0)
    ap.add_argument("--bucket-hi", type=int, default=255)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--bench", type=int, metavar="N")
    ap.add_argument("--parity", type=int, metavar="N")
    ap.add_argument("--hourly", type=float, default=0.72)
    a = ap.parse_args()

    lo, hi = a.bucket_lo, a.bucket_hi
    if not 0 <= lo <= hi <= 255:
        ap.error(f"bad bucket range {lo}-{hi}; need 0 <= lo <= hi <= 255")

    if a.status:
        return report(load_names(lo, hi), lo, hi)
    if a.bench:
        return bench(a.bench, a.hourly, lo, hi)
    if a.parity:
        if not a.model:
            ap.error("--parity needs --model")
        return parity(a.model, a.parity)

    tags = [t.strip() for t in a.models.split(",") if t.strip()]
    for t in tags:
        block_for(t)  # validate all tags before loading a single model
    signal.signal(signal.SIGINT, _on_sigint)
    by_bucket = load_names(lo, hi)
    total = sum(len(v) for v in by_bucket.values())
    print(f"buckets {lo}-{hi}: {total:,} names | blocks: {', '.join(tags)}", flush=True)
    t0 = time.monotonic()
    for t in tags:
        try:
            run(t, by_bucket, lo, hi)
        except KeyboardInterrupt:
            sys.exit(130)
    print(f"\nALL BLOCKS DONE in {(time.monotonic() - t0) / 3600:.2f}h", flush=True)


if __name__ == "__main__":
    main()
