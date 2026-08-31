"""Embed Jero's half (hash buckets 0-127) of the 3.82M-name universe.

Mirror of the embed_run packet William got, pointed at this machine's half and
writing straight into the canonical store at data/prices/enrich/_embed_store/.
Uses the repo's own prices.enrich modules, so the vectors are bit-comparable
with the ~284k already in the store.

    PYTHONPATH=src ./.venv/bin/python src/prices/enrich/gpu/jero_embed.py --model 4b
    PYTHONPATH=src ./.venv/bin/python src/prices/enrich/gpu/jero_embed.py --status

Resume is disk-derived: the store IS the progress record. Re-run the same
command to continue. Ctrl-C finishes the current chunk and exits.
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
MY_HALF = 0
MY_BUCKET_LO, MY_BUCKET_HI = 0, 127
CHECKPOINT_EVERY = 2000

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


def load_my_names() -> dict[int, list[str]]:
    df = pd.read_parquet(SPLIT, columns=["product_name_original", "bucket", "half"])
    mine = df[df["half"] == MY_HALF]
    lo, hi = int(mine["bucket"].min()), int(mine["bucket"].max())
    if lo < MY_BUCKET_LO or hi > MY_BUCKET_HI:
        sys.exit(
            f"FATAL: names hash to buckets {lo}-{hi}, expected {MY_BUCKET_LO}-{MY_BUCKET_HI}"
        )
    out: dict[int, list[str]] = {}
    for b, g in mine.groupby("bucket"):
        names = list(dict.fromkeys(g["product_name_original"].astype(str)))
        out[int(b)] = names
    return out


def block_for(tag: str) -> dict:
    for blk in config.CLASSIFIER_EMBED_ENSEMBLE:
        if blk["tag"] == tag:
            return blk
    sys.exit(f"unknown model tag {tag}")


def report(by_bucket: dict[int, list[str]]) -> None:
    total = sum(len(v) for v in by_bucket.values())
    print(f"{'model':<8}{'stored':>12}{'missing':>12}{'pct':>8}")
    for blk in config.CLASSIFIER_EMBED_ENSEMBLE:
        tag = blk["tag"]
        have = 0
        for b, names in by_bucket.items():
            have += len(set(names) & bucket_keys(tag, b))
        miss = total - have
        print(f"{tag:<8}{have:>12,}{miss:>12,}{100*have/total:>7.1f}%")
    print(f"{'TOTAL':<8}{total:>12,}")


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
    by_bucket = load_my_names()
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

    lock = single_run_lock(tag)
    signal.signal(signal.SIGINT, _on_sigint)
    worker = embedding.MlxWorker(blk["model"]) if blk["backend"] == "mlx" else None
    done, t_start = 0, time.monotonic()
    try:
        for b in sorted(todo):
            names = todo[b]
            for i in range(0, len(names), CHECKPOINT_EVERY):
                if _stop:
                    raise KeyboardInterrupt
                chunk = names[i : i + CHECKPOINT_EVERY]
                t0 = time.monotonic()
                try:
                    vecs = (
                        worker.encode(blk, chunk)
                        if worker
                        else embedding.encode_st_block(blk, chunk)
                    )
                except RuntimeError:
                    if _stop:
                        raise KeyboardInterrupt
                    raise
                embed_store.append(tag, b, chunk, vecs)
                done += len(chunk)
                dt = time.monotonic() - t0
                rate = done / max(time.monotonic() - t_start, 1e-9)
                eta_h = (left - done) / rate / 3600 if rate else float("nan")
                print(
                    f"[{tag}] bucket {b:03d} +{len(chunk)} in {dt:.0f}s "
                    f"| {done:,}/{left:,} | {1000/rate:.0f}ms/name | ETA {eta_h:.1f}h",
                    flush=True,
                )
    except KeyboardInterrupt:
        print(
            f"[{tag}] stopped cleanly at {done:,}/{left:,}. Re-run to resume.",
            flush=True,
        )
    finally:
        if worker:
            worker.close()
        if not worker:
            embedding.free_st()
        lock.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["0p6b", "4b", "8b_q8"])
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        report(load_my_names())
        return
    if not a.model:
        ap.error("pass --model {0p6b,4b,8b_q8} or --status")
    run(a.model)


if __name__ == "__main__":
    main()
