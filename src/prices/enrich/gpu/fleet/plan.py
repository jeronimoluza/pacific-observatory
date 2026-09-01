"""Partition the embed universe into disjoint per-pod bucket ranges.

    PYTHONPATH=src python src/prices/enrich/gpu/fleet/plan.py --pods 12 > fleet/pods.txt

bucket_of(name) is a pure function of the name, so a name belongs to exactly one
bucket and therefore to exactly one pod: disjoint --bucket-lo/--bucket-hi ranges
cover the universe with no name embedded twice and no coordination between pods.
That property is the whole reason the fleet needs no locking, so it is verified
here rather than assumed -- the per-pod counts must sum to the universe exactly.

Ranges are balanced by NAME count, not by bucket count. Buckets are near-uniform
in practice, but a range split on bucket index alone would still leave the pods
finishing at different times, and the fleet is only as fast as its slowest pod.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

UNIVERSE = Path(
    os.environ.get(
        "EMBED_UNIVERSE",
        "data/prices/_enrich/transfer/embed_universe_cc_20260901.parquet",
    )
)


def bucket_counts() -> np.ndarray:
    t = pq.read_table(UNIVERSE, columns=["bucket"])
    return np.bincount(t.column("bucket").to_numpy(), minlength=256).astype(np.int64)


def split(counts: np.ndarray, pods: int) -> list[tuple[int, int]]:
    """Contiguous bucket ranges whose name counts are as even as possible."""
    total = int(counts.sum())
    cum = np.cumsum(counts)
    out, lo = [], 0
    for i in range(pods):
        if lo > 255:
            break
        target = total * (i + 1) / pods
        hi = int(np.searchsorted(cum, target)) if i < pods - 1 else 255
        hi = max(lo, min(hi, 255))
        out.append((lo, hi))
        lo = hi + 1
    if out and out[-1][1] != 255:
        out[-1] = (out[-1][0], 255)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pods", type=int, default=12)
    a = ap.parse_args()
    if not 1 <= a.pods <= 256:
        ap.error("--pods must be 1..256")
    if not UNIVERSE.exists():
        sys.exit(f"universe not found: {UNIVERSE}")

    counts = bucket_counts()
    total = int(counts.sum())
    ranges = split(counts, a.pods)

    covered = np.zeros(256, dtype=np.int64)
    seen = 0
    print(f"# universe: {UNIVERSE}", file=sys.stderr)
    print(f"# {total:,} names over {len(ranges)} pods", file=sys.stderr)
    print(f"# {'pod':<5}{'lo':>5}{'hi':>5}{'names':>14}", file=sys.stderr)
    for i, (lo, hi) in enumerate(ranges, 1):
        n = int(counts[lo : hi + 1].sum())
        covered[lo : hi + 1] += 1
        seen += n
        print(f"# {'pod' + str(i):<5}{lo:>5}{hi:>5}{n:>14,}", file=sys.stderr)
        # id host port lo hi -- fill host/port in before launch
        print(f"pod{i}\tHOST\tPORT\t{lo}\t{hi}")

    ok = seen == total and covered.min() == 1 and covered.max() == 1
    print(
        f"# partition: sum={seen:,} vs universe={total:,}; "
        f"each bucket covered {covered.min()}..{covered.max()}x -> "
        f"{'OK' if ok else 'BROKEN'}",
        file=sys.stderr,
    )
    if not ok:
        sys.exit("refusing to emit a plan that does not partition the universe")


if __name__ == "__main__":
    main()
