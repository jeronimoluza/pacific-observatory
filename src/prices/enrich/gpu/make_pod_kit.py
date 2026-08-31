"""Build the RunPod rehearsal kit: a small name subset + a self-contained tarball.

    PYTHONPATH=src ./.venv/bin/python src/prices/enrich/gpu/make_pod_kit.py --n 20000

Picks names that ALREADY have both 0p6b and 4b MLX vectors on this machine, so
the vectors that come back can be scored for backend agreement (E1) without
uploading anything else. Spreads them over several buckets so a kill/resume test
lands mid-bucket.
"""

from __future__ import annotations

import argparse
import subprocess
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
STORE = REPO / "data/prices/enrich/_embed_store"
SPLIT = REPO / "data/prices/_enrich/transfer/embed_names_split_20260819.parquet"
OUT_DIR = REPO / "data/prices/_enrich/pod_kit"
BUCKETS = list(range(8))


def build_subset(n: int) -> Path:
    per = n // len(BUCKETS)
    df = pd.read_parquet(SPLIT, columns=["product_name_original", "bucket"])
    df = df[df["bucket"].isin(BUCKETS)]
    rows = []
    for b in BUCKETS:
        have = None
        for tag in ("0p6b", "4b"):
            p = STORE / tag / f"bucket_{b:03d}.npz"
            with np.load(p, allow_pickle=False) as z:
                keys = {str(k) for k in z["keys"]}
            have = keys if have is None else (have & keys)
        g = df[df["bucket"] == b]
        g = g[g["product_name_original"].astype(str).isin(have)].head(per)
        rows.append(g)
        print(f"  bucket {b:03d}: {len(g):,} names with both 0p6b+4b vectors")
    sub = pd.concat(rows, ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "rehearsal_names.parquet"
    sub.to_parquet(out, index=False)
    print(f"subset: {len(sub):,} names -> {out} ({out.stat().st_size/1e6:.2f} MB)")
    return out


def build_tarball(subset: Path) -> Path:
    tar_path = OUT_DIR / "pod_kit.tar.gz"
    # Layout inside the tar mirrors REPO_ROOT so config.py's parents[3] resolves
    # to /workspace/repo and the store lands on the network volume.
    members = [
        (REPO / "src/prices", "repo/src/prices"),
        (
            subset,
            "repo/data/prices/_enrich/transfer/embed_names_split_20260819.parquet",
        ),
    ]
    with tarfile.open(tar_path, "w:gz") as tf:
        for src, arc in members:
            tf.add(
                src,
                arcname=arc,
                filter=lambda ti: None
                if ("__pycache__" in ti.name or ti.name.endswith(".pyc"))
                else ti,
            )
    print(f"tarball: {tar_path} ({tar_path.stat().st_size/1e6:.2f} MB)")
    return tar_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    a = ap.parse_args()
    subset = build_subset(a.n)
    tar = build_tarball(subset)
    print("\nsha256:")
    print(
        subprocess.run(
            ["shasum", "-a", "256", str(tar)], capture_output=True, text=True
        ).stdout.strip()
    )


if __name__ == "__main__":
    main()
