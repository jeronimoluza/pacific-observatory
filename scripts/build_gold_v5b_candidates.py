"""Grow gold v5 3k->5k: incremental leaf-coverage candidate sampler (W3.1 supplement).

Adds N new candidates DISJOINT from the frozen 3k, biased to cover COICOP leaves
absent or thin in current gold. Three sub-pools:
  - green    : GREEN decisions, leaf-balanced over the earned cascade leaf toward
               absent/thin gold leaves -> guaranteed *real* leaf breadth (food).
  - reject   : EXCLUDE/OTHER_FORM decisions, representative -> reject-boundary
               signal for the gate calibration step (NOT counted as coverage).
  - unscoped : broad corpus, diversity-maximized over country x script x retailer
               category -> lets the LLM passes DISCOVER non-food leaves the
               food-biased v0 classifier can't route to.
Emits NEW files only (never overwrites the frozen 3k): gold_v5b_candidates.parquet,
gold_v5b_manifest.json, and batch CSVs continuing the 3k numbering (020+).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prices.enrich import config  # noqa: E402
from prices.enrich.base_items import store  # noqa: E402
from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index  # noqa: E402

from build_gold_v5_candidates import (  # noqa: E402
    BATCH_DIR,
    DIV_ABSENT_MULT,
    GOLD_DIR,
    KEEP_COLS,
    OVERSAMPLE_SCRIPTS,
    PRODUCT_DECISIONS_CSV,
    SCRIPT_MULT,
    _division,
    _vec_norm,
    _weighted_sample,
    script_of,
)

SEED = 20260709
N_EXISTING = 3000
FIRST_NEW_BATCH = N_EXISTING // 150
CANDIDATES_PATH = GOLD_DIR / "gold_v5b_candidates.parquet"
MANIFEST_PATH = GOLD_DIR / "gold_v5b_manifest.json"
FINAL_3K = GOLD_DIR / "gold_v5_final.parquet"
MANIFEST_3K = GOLD_DIR / "gold_v5_manifest.json"
ABSENT_W = 3.0
THIN_W = 1.8
QUOTA_ABSENT = 14
QUOTA_THIN = 7
QUOTA_COVERED = 3
GREEN_FRAC = 0.25
REJECT_FRAC = 0.15
NAN_COLS = [
    "channel",
    "price",
    "input_hash",
    "dedup_cluster_id",
    "category",
    "declared_coicop_codes",
]
BATCH_COLS = [
    "gold_row_id",
    "product_name_original",
    "country",
    "source",
    "channel",
    "category",
    "declared_coicop_codes",
    "price",
]


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(config.REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _existing_keys() -> set:
    keys = set()
    man = json.loads(MANIFEST_3K.read_text(encoding="utf-8"))
    keys |= set(man.get("cluster_disjoint", {}).get("norm_keys", []))
    g = pd.read_parquet(FINAL_3K, columns=["product_name"])
    keys |= set(_vec_norm(g["product_name"]))
    return keys


def _gold_leaf_counts() -> dict:
    g = pd.read_parquet(FINAL_3K, columns=["verdict", "code"])
    return g[g["verdict"] == "leaf"]["code"].value_counts().to_dict()


def _quota(count: int) -> int:
    if count == 0:
        return QUOTA_ABSENT
    if count <= 3:
        return QUOTA_THIN
    return QUOTA_COVERED


def _gap_weight(count: int) -> float:
    if count == 0:
        return ABSENT_W
    if count <= 3:
        return THIN_W
    return 1.0


def _rand_state(rng) -> int:
    return int(rng.integers(0, 2**31 - 1))


def _decisions(decisions: list) -> pd.DataFrame:
    dec = pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str)
    dec = dec[dec["decision"].isin(decisions)].copy()
    dec["norm_key"] = _vec_norm(dec["product_name"])
    dec = dec[dec["norm_key"].str.len() >= 2].drop_duplicates("norm_key")
    return dec


def _finish(pick: pd.DataFrame, half: str) -> pd.DataFrame:
    pick = pick.copy()
    pick["half"] = half
    pick["product_name_original"] = pick["product_name"]
    pick["script"] = pick["product_name"].map(script_of)
    for c in NAN_COLS:
        if c not in pick.columns:
            pick[c] = np.nan
    return pick


def _green_half(n, exclude, gold_counts, leaves, rng) -> pd.DataFrame:
    dec = _decisions(["GREEN"])
    dec = dec[~dec["norm_key"].isin(exclude)]
    dec = dec[dec["coicop_deep_leaf_code"].isin(leaves)].copy()
    dec["leaf"] = dec["coicop_deep_leaf_code"]
    order = sorted(
        dec["leaf"].unique(),
        key=lambda lf: (gold_counts.get(lf, 0), -int((dec["leaf"] == lf).sum())),
    )
    picked = [
        dec[dec["leaf"] == lf].sample(
            n=min(int((dec["leaf"] == lf).sum()), _quota(gold_counts.get(lf, 0))),
            random_state=_rand_state(rng),
        )
        for lf in order
    ]
    pick = pd.concat(picked, ignore_index=True)
    if len(pick) >= n:
        pick = pick.head(n)
    else:
        rem = dec[~dec["norm_key"].isin(set(pick["norm_key"]))]
        w = rem["leaf"].map(lambda lf: _gap_weight(gold_counts.get(lf, 0)))
        w = (w / w.sum()).to_numpy()
        take = min(n - len(pick), len(rem))
        idx = rng.choice(rem.index.to_numpy(), size=take, replace=False, p=w)
        pick = pd.concat([pick, rem.loc[idx]], ignore_index=True)
    pick["division"] = pick["leaf"].map(_division)
    pick["sampling_stratum"] = "green|" + pick["leaf"]
    return _finish(pick, "leaf_coverage_green")


def _reject_half(n, exclude, rng) -> pd.DataFrame:
    dec = _decisions(["EXCLUDE", "OTHER_FORM"])
    dec = dec[~dec["norm_key"].isin(exclude)].copy()
    dec["division"] = dec["coicop_deep_leaf_code"].map(_division)
    dec["sampling_stratum"] = (
        dec["decision"] + "|" + dec["division"] + "|" + dec["country"].astype(str)
    )
    parts = []
    for i, d in enumerate(["EXCLUDE", "OTHER_FORM"]):
        sub = dec[dec["decision"] == d].reset_index(drop=True)
        take = n - (n // 2) if i == 0 else n // 2
        parts.append(_weighted_sample(sub, take, None, rng))
    pick = pd.concat(parts, ignore_index=True)
    return _finish(pick, "reject_boundary")


def _unscoped_half(n, exclude, green_divs, rng) -> pd.DataFrame:
    cols = [
        "input_hash",
        "product_name_original",
        "category",
        "country",
        "channel",
        "declared_coicop_codes",
        "price",
        "source",
    ]
    pi = pd.read_parquet(config.PRODUCTS_INPUT_PARQUET, columns=cols)
    pi["norm_key"] = _vec_norm(pi["product_name_original"])
    pi = pi[pi["norm_key"].str.len() >= 2]
    owned = set(
        _vec_norm(
            pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str, usecols=["product_name"])[
                "product_name"
            ]
        )
    )
    alias_tokens = set(store.head_alias_index().keys())
    uns = (
        pi[~pi["norm_key"].isin(owned) & ~pi["norm_key"].isin(exclude)]
        .drop_duplicates("norm_key")
        .reset_index(drop=True)
    )
    uns["script"] = uns["product_name_original"].map(script_of)
    uns["cat"] = uns["category"].fillna("none").astype(str).str.lower().str[:40]
    uns["division"] = uns["declared_coicop_codes"].map(_division)
    # diversity stratum: country x script x retailer-category breadcrumb
    uns["sampling_stratum"] = (
        uns["country"].astype(str) + "|" + uns["script"] + "|" + uns["cat"]
    )
    mult = np.ones(len(uns))
    mult = np.where(uns["script"].isin(OVERSAMPLE_SCRIPTS), mult * SCRIPT_MULT, mult)
    mult = np.where(~uns["division"].isin(green_divs), mult * DIV_ABSENT_MULT, mult)
    draw = min(len(uns), int(n * 1.4))
    pool = _weighted_sample(uns, draw, pd.Series(mult, index=uns.index), rng).copy()
    tok_owned = pool["norm_key"].map(lambda k: bool(set(k.split()) & alias_tokens))
    pool = pool[~tok_owned].head(n).copy()
    pool["half"] = "leaf_coverage_unscoped"
    pool["dedup_cluster_id"] = np.nan
    return pool


def build(target: int) -> tuple:
    rng = np.random.default_rng(SEED)
    leaves, _ = load_taxonomy_index()
    exclude = _existing_keys()
    gold_counts = _gold_leaf_counts()
    gold_leaves = {lf for lf, c in gold_counts.items() if c > 0}

    dec_all = _decisions(["GREEN"])
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
        "supplements": "gold_v5_final.parquet (3000)",
        "strategy": (
            "leaf-coverage supplement: green=GREEN leaf-balanced (guaranteed real "
            "breadth); reject=representative EXCLUDE/OTHER_FORM (boundary signal); "
            "unscoped=country x script x category diversity (LLM discovers non-food "
            "leaves). Disjoint from the frozen 3k by norm_key."
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
            "mechanism": "norm_key disjoint from frozen 3k (manifest + final names)",
            "norm_keys": sorted(out["norm_key"].dropna().unique().tolist()),
        },
        "n_batches": (len(out) + 149) // 150,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=2000)
    args = ap.parse_args()
    out, man = build(args.target)
    print(f"gold v5b candidates: {len(out)} rows -> {CANDIDATES_PATH}")
    print(
        f"  green={man['n_green']} reject={man['n_reject']} unscoped={man['n_unscoped']}"
    )
    print(f"  batches {man['batch_range']} -> {BATCH_DIR}")
    print(
        f"  green guaranteed NEW leaves vs gold: {man['green_guaranteed_new_leaves']}"
    )
    print(f"  scripts: {man['composition']['by_script']}")


if __name__ == "__main__":
    main()
