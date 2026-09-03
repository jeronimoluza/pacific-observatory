"""Score the embedding store bucket-major, across processes, without OOM.

A worker holds exactly one bucket at a time, so peak resident memory is
``workers x (one gathered bucket + one copy of the model)`` and nothing in it
grows with the corpus. The bucket is also the only partition that parallelises
for free: a name's bucket is ``sha1(name)[:4] % 256``, so two workers never want
the same bucket file and no state has to be shared between them.

**Cores are not the limit here, memory is.** A gathered bucket of the four
production blocks is around a gigabyte, so a 16-core box that naively runs 16
workers asks for ~16 GB of bucket on top of 16 copies of the model, and dies
hours into a run with most of the work unsaved. `plan_workers` divides the
budget by what one worker actually costs — measured from the bucket files on
disk, because ``np.savez`` is uncompressed and a bucket's fp16 matrix is its
file size — and clamps to that. Asking for more workers than fit gets you fewer
workers, printed, rather than an OOM.

Work is handed out longest-bucket-first. Bucket sizes are uneven (names are not
distributed evenly across a sha1 mod), and starting the big ones last leaves one
worker running alone at the end.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Sequence

from prices.enrich import config
from prices.enrich.classifier import embed_store

# A bucket is stored fp16 and gathered to fp32 (x2), and the per-tag matrices are
# then hstacked into one more copy of the result (x2 again). Four is the observed
# ceiling of that chain rather than a guess with headroom baked in.
GATHER_FACTOR = 4


def total_memory_bytes() -> int:
    """Physical RAM. `os.sysconf` carries it on both Linux and macOS; anything
    else gets a deliberately small answer so the clamp stays conservative."""
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return 8 * 1024**3


def budget_bytes() -> int:
    """What a parallel score is allowed to occupy, in bytes."""
    if config.CLASSIFY_MEM_BUDGET_GB > 0:
        return int(config.CLASSIFY_MEM_BUDGET_GB * 1024**3)
    return int(total_memory_bytes() * config.CLASSIFY_MEM_BUDGET_FRACTION)


def bucket_bytes(bucket: int, tags: Sequence[str]) -> int:
    """On-disk size of one bucket across every block, which is also its fp16
    size in memory — the store is written with `np.savez`, uncompressed."""
    total = 0
    for tag in tags:
        path = embed_store.STORE_DIR / tag / f"bucket_{bucket:03d}.npz"
        if path.exists():
            total += path.stat().st_size
    return total


def worker_bytes(buckets: Iterable[int], tags: Sequence[str], model_bytes: int) -> int:
    """Peak cost of one worker: its largest bucket, gathered, plus the model.

    The largest and not the mean, because the schedule hands every worker the
    big buckets first — a mean-sized estimate is the number that OOMs.
    """
    sizes = [bucket_bytes(b, tags) for b in buckets]
    return max(sizes, default=0) * GATHER_FACTOR + model_bytes


def plan_workers(
    requested: int,
    buckets: Iterable[int],
    tags: Sequence[str],
    model_bytes: int = 0,
    budget: int | None = None,
) -> int:
    """How many workers actually fit. Never returns less than 1 — a single
    worker is the sequential path, which is always allowed to run."""
    buckets = list(buckets)
    per_worker = worker_bytes(buckets, tags, model_bytes)
    if per_worker <= 0:
        return max(1, min(requested, len(buckets) or 1))
    fits = int((budget if budget is not None else budget_bytes()) // per_worker)
    return max(1, min(requested, len(buckets) or 1, fits))


def map_buckets(
    work: Callable[[tuple], Path | None],
    items: Sequence[tuple],
    workers: int = 1,
    tags: Sequence[str] = (),
    model_bytes: int = 0,
    label: str = "score",
) -> list:
    """Run `work` over `items`, longest bucket first, within the memory budget.

    Each item is a tuple whose first element is the bucket number; the rest is
    whatever `work` needs. `work` must be importable at module level — it is
    pickled to the child processes — and should write its own output shard, so a
    killed run resumes from disk rather than from this function's return value.
    """
    if not items:
        return []
    ordered = sorted(items, key=lambda it: -len(it[1]))
    n = plan_workers(workers, [it[0] for it in ordered], tags, model_bytes)
    if n < workers:
        print(
            f"[{label}] {workers} workers requested, running {n}: "
            f"{worker_bytes([it[0] for it in ordered], tags, model_bytes) / 1e9:.1f} GB "
            f"each against a {budget_bytes() / 1e9:.1f} GB budget",
            flush=True,
        )
    if n == 1:
        return [work(it) for it in ordered]
    with ProcessPoolExecutor(max_workers=n) as pool:
        return list(pool.map(work, ordered))
