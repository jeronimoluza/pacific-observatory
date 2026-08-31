"""Score downloaded GPU vectors against the MLX vectors in the local store.

    ./.venv/bin/python src/prices/enrich/gpu/score_parity.py \
        --downloaded data/prices/_enrich/pod_kit/downloaded --tag 4b

Reads only; writes nothing. The downloaded tree must NOT be merged into the
canonical store until the verdict here is green.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
STORE = REPO / "data/prices/enrich/_embed_store"


def load(d: Path, tag: str) -> dict[str, np.ndarray]:
    out = {}
    for p in sorted((d / tag).glob("bucket_*.npz")):
        with np.load(p, allow_pickle=False) as z:
            for k, v in zip(z["keys"], z["mat"]):
                out[str(k)] = v.astype(np.float32)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--downloaded", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ref-tag", help="local tag to compare against (default: same)")
    a = ap.parse_args()

    gpu = load(Path(a.downloaded), a.tag)
    ref = load(STORE, a.ref_tag or a.tag)
    shared = sorted(set(gpu) & set(ref))
    print(f"gpu {len(gpu):,} | local {len(ref):,} | overlap {len(shared):,}")
    if not shared:
        print("NO OVERLAP - nothing to score")
        return

    G = np.vstack([gpu[k] for k in shared])
    R = np.vstack([ref[k] for k in shared])
    if G.shape[1] != R.shape[1]:
        print(f"DIM MISMATCH gpu={G.shape[1]} local={R.shape[1]} - not comparable")
        return
    G /= np.linalg.norm(G, axis=1, keepdims=True) + 1e-9
    R /= np.linalg.norm(R, axis=1, keepdims=True) + 1e-9
    cos = np.sum(G * R, axis=1)

    print(
        f"cosine  mean {cos.mean():.6f}  p50 {np.percentile(cos,50):.6f}  "
        f"p01 {np.percentile(cos,1):.6f}  min {cos.min():.6f}"
    )
    for thr in (0.9999, 0.999, 0.99, 0.95):
        print(f"  frac below {thr:<7}: {(cos < thr).mean():.4%}")

    # Rank-order agreement: does the GPU space preserve nearest neighbours?
    k = min(2000, len(shared))
    idx = np.random.default_rng(0).choice(len(shared), k, replace=False)
    sg = G[idx] @ G[idx].T
    sr = R[idx] @ R[idx].T
    np.fill_diagonal(sg, -np.inf)
    np.fill_diagonal(sr, -np.inf)
    tg = np.argsort(-sg, axis=1)[:, :10]
    tr = np.argsort(-sr, axis=1)[:, :10]
    ov = np.mean([len(set(a_) & set(b_)) / 10 for a_, b_ in zip(tg, tr)])
    print(f"top-10 neighbour overlap on {k:,} sampled rows: {ov:.3f}")

    print(
        "VERDICT:",
        "REUSABLE - existing vectors can be extended on GPU"
        if np.percentile(cos, 1) >= 0.999 and ov >= 0.95
        else "NOT REUSABLE - re-embed this tier under its own tag",
    )


if __name__ == "__main__":
    main()
