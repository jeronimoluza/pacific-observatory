"""Grow gold v5 5k->8k: incremental leaf-coverage candidate sampler (W3.1 supplement 2).

Adds N new candidates DISJOINT from the frozen 5k, biased to cover COICOP leaves
still absent or thin AFTER the 5k round. Reuses the three sub-pool builders from
the 3k->5k supplement (green / reject / unscoped) unchanged; only the anchoring
constants move (existing=5000, gold_counts from the 5k final's 283 leaves, row-id
offset 5000, batch numbering continues at 034). Emits NEW files only (never
overwrites the frozen 5k): gold_v5c_candidates.parquet, gold_v5c_manifest.json,
and batch CSVs continuing the numbering (034+).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index  # noqa: E402

from build_gold_v5_candidates import (  # noqa: E402
    BATCH_DIR,
    GOLD_DIR,
    KEEP_COLS,
    PRODUCT_DECISIONS_CSV,
    _division,
    _vec_norm,
)
from build_gold_v5b_candidates import (  # noqa: E402
    BATCH_COLS,
    GREEN_FRAC,
    QUOTA_ABSENT,
    QUOTA_COVERED,
    QUOTA_THIN,
    REJECT_FRAC,
    _git_sha,
    _green_half,
    _reject_half,
    _unscoped_half,
)

SEED = 20260710
N_EXISTING = 5000
FIRST_NEW_BATCH = 34
CANDIDATES_PATH = GOLD_DIR / "gold_v5c_candidates.parquet"
MANIFEST_PATH = GOLD_DIR / "gold_v5c_manifest.json"
FINAL_5K = GOLD_DIR / "gold_v5_5k_final.parquet"
MANIFEST_3K = GOLD_DIR / "gold_v5_manifest.json"
MANIFEST_5B = GOLD_DIR / "gold_v5b_manifest.json"


def _existing_keys() -> set:
    keys = set()
    for man_path in (MANIFEST_3K, MANIFEST_5B):
        man = json.loads(man_path.read_text(encoding="utf-8"))
        keys |= set(man.get("cluster_disjoint", {}).get("norm_keys", []))
    g = pd.read_parquet(FINAL_5K, columns=["product_name"])
    keys |= set(_vec_norm(g["product_name"]))
    return keys


def _gold_leaf_counts() -> dict:
    g = pd.read_parquet(FINAL_5K, columns=["verdict", "code"])
    return g[g["verdict"] == "leaf"]["code"].value_counts().to_dict()


def build(target: int) -> tuple:
    rng = np.random.default_rng(SEED)
    leaves, _ = load_taxonomy_index()
    exclude = _existing_keys()
    gold_counts = _gold_leaf_counts()
    gold_leaves = {lf for lf, c in gold_counts.items() if c > 0}

    dec_all = pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str)
    dec_all = dec_all[dec_all["decision"] == "GREEN"]
    green_divs = set(dec_all["coicop_deep_leaf_code"].dropna().map(_division).unique())

    n_green = int(target * GREEN_FRAC)
    n_reject = int(target * REJECT_FRAC)
    n_uns = target - n_green - n_reject

    green = _green_half(n_green, exclude, gold_counts, leaves, rng)
    exclude = exclude | set(green["norm_key"])
    reject = _reject_half(n_reject, exclude, rng)
    exclude = exclude | set(reject["norm_key"])
    uns = _unscoped_half(n_uns, exclude, green_divs, rng)

    out = pd.concat([green, reject, uns], ignore_index=True)
    out["gold_row_id"] = [f"gv5-{N_EXISTING + i:05d}" for i in range(len(out))]
    for c in KEEP_COLS:
        if c not in out.columns:
            out[c] = np.nan
    out = out[KEEP_COLS]
    out.to_parquet(CANDIDATES_PATH, index=False)

    for b, start in enumerate(range(0, len(out), 150)):
        out.iloc[start : start + 150][BATCH_COLS].to_csv(
            BATCH_DIR / f"gold_v5_batch_{FIRST_NEW_BATCH + b:03d}.csv", index=False
        )

    green_leaves = set(green["sampling_stratum"].str.split("|").str[-1])
    new_green = sorted(green_leaves - gold_leaves)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": _git_sha(),
        "seed": SEED,
        "target": target,
        "supplements": "gold_v5_5k_final.parquet (5000)",
        "strategy": (
            "leaf-coverage supplement 2: green=GREEN leaf-balanced toward leaves "
            "still thin after the 5k; reject=representative EXCLUDE/OTHER_FORM; "
            "unscoped=country x script x category diversity. Disjoint from the "
            "frozen 5k by norm_key (5k-final names + 3k/5b manifest norm_keys)."
        ),
        "n_total": int(len(out)),
        "n_green": int(len(green)),
        "n_reject": int(len(reject)),
        "n_unscoped": int(len(uns)),
        "gold_row_id_range": [out["gold_row_id"].iloc[0], out["gold_row_id"].iloc[-1]],
        "batch_range": [FIRST_NEW_BATCH, FIRST_NEW_BATCH + (len(out) + 149) // 150 - 1],
        "quotas": {
            "absent": QUOTA_ABSENT,
            "thin": QUOTA_THIN,
            "covered": QUOTA_COVERED,
        },
        "green_guaranteed_new_leaves": len(new_green),
        "green_new_leaves": new_green,
        "green_distinct_leaves": len(green_leaves),
        "gold_leaves_before": len(gold_leaves),
        "composition": {
            "by_half": out["half"].value_counts().to_dict(),
            "by_script": out["script"].value_counts().to_dict(),
            "by_division": out["division"].value_counts().to_dict(),
        },
        "cluster_disjoint": {
            "mechanism": "norm_key disjoint from frozen 5k (5k final names + 3k/5b manifests)",
            "norm_keys": sorted(out["norm_key"].dropna().unique().tolist()),
        },
        "n_batches": (len(out) + 149) // 150,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=3000)
    args = ap.parse_args()
    out, man = build(args.target)
    print(f"gold v5c candidates: {len(out)} rows -> {CANDIDATES_PATH}")
    print(
        f"  green={man['n_green']} reject={man['n_reject']} unscoped={man['n_unscoped']}"
    )
    print(f"  batches {man['batch_range']} -> {BATCH_DIR}")
    print(
        f"  green guaranteed NEW leaves vs 5k gold: {man['green_guaranteed_new_leaves']}"
    )
    print(f"  scripts: {man['composition']['by_script']}")


if __name__ == "__main__":
    main()
