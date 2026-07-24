"""Build gold v5 candidate pool (W3.1 of the consensus classification runbook).

Deterministic, seeded stratified sampler. ~50% from the decisions ledger
(GREEN + OTHER_FORM + EXCLUDE, so gold judges rejects too), ~50% from the
unscoped corpus (products_input names owned by no base_item), with deliberate
oversampling of CJK/JA/Thai/Cyrillic scripts and COICOP divisions absent from
GREEN. Emits gold_v5_candidates.parquet + gold_v5_manifest.json (norm-keys +
dedup cluster ids for cluster-disjoint training in W2.1) + <=150-row batch CSVs.
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

from prices.enrich import config  # noqa: E402
from prices.enrich.base_items import store  # noqa: E402

SEED = 20260707
GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
CANDIDATES_PATH = GOLD_DIR / "gold_v5_candidates.parquet"
MANIFEST_PATH = GOLD_DIR / "gold_v5_manifest.json"
BATCH_DIR = GOLD_DIR / "batches"
PRODUCT_DECISIONS_CSV = (
    config.REPO_ROOT / "outputs" / "prices" / "validation" / "product_decisions.csv"
)

DECISION_KEEP = ["GREEN", "OTHER_FORM", "EXCLUDE"]
OVERSAMPLE_SCRIPTS = {
    "cjk_han",
    "japanese_kana",
    "hangul",
    "thai",
    "cyrillic",
    "arabic",
}
SCRIPT_MULT = 3.0
DIV_ABSENT_MULT = 2.0
KEEP_COLS = [
    "gold_row_id",
    "half",
    "product_name_original",
    "country",
    "source",
    "channel",
    "category",
    "declared_coicop_codes",
    "price",
    "script",
    "division",
    "sampling_stratum",
    "norm_key",
    "input_hash",
    "dedup_cluster_id",
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


def script_of(text: str) -> str:
    s = str(text)
    has_kana = any("぀" <= c <= "ヿ" for c in s)
    if has_kana:
        return "japanese_kana"
    for c in s:
        if "가" <= c <= "힣":
            return "hangul"
        if "฀" <= c <= "๿":
            return "thai"
        if "Ѐ" <= c <= "ӿ":
            return "cyrillic"
        if "؀" <= c <= "ۿ":
            return "arabic"
        if "一" <= c <= "鿿":
            return "cjk_han"
    return "latin"


def _vec_norm(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.lower()
        .str.replace(r"[\W_]+", " ", regex=True)
        .str.strip()
    )


def _division(code: str) -> str:
    c = str(code).split(";")[0].split(",")[0].strip()
    return c[:2] if len(c) >= 2 and c[:2].isdigit() else "none"


def _weighted_sample(
    df: pd.DataFrame, n: int, extra_mult: pd.Series | None, rng
) -> pd.DataFrame:
    if len(df) <= n:
        return df
    counts = df.groupby("sampling_stratum")["sampling_stratum"].transform("size")
    w = 1.0 / np.sqrt(counts.to_numpy(dtype=float))
    if extra_mult is not None:
        w = w * extra_mult.to_numpy(dtype=float)
    w = w / w.sum()
    idx = rng.choice(df.index.to_numpy(), size=n, replace=False, p=w)
    return df.loc[idx]


def _owned_keys() -> set:
    d = pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str, usecols=["product_name"])
    return set(_vec_norm(d["product_name"]))


def build(target: int) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    owned_keys = _owned_keys()
    alias_tokens = set(store.head_alias_index().keys())

    # ---- decisions half ----
    dec = pd.read_csv(PRODUCT_DECISIONS_CSV, dtype=str)
    dec = dec[dec["decision"].isin(DECISION_KEEP)].copy()
    dec["norm_key"] = _vec_norm(dec["product_name"])
    dec = dec[dec["norm_key"].str.len() >= 2].drop_duplicates("norm_key")
    dec["script"] = dec["product_name"].map(script_of)
    dec["division"] = dec["coicop_deep_leaf_code"].map(_division)
    dec["sampling_stratum"] = (
        dec["decision"] + "|" + dec["division"] + "|" + dec["country"]
    )
    green_divs = set(dec.loc[dec["decision"] == "GREEN", "division"].unique())

    dec = dec.reset_index(drop=True)
    n_dec = target // 2
    # stratify OVER decision: even budget per decision, then sqrt(leaf|country) within
    per_dec = n_dec // len(DECISION_KEEP)
    parts = []
    for i, decision in enumerate(DECISION_KEEP):
        sub = dec[dec["decision"] == decision].reset_index(drop=True)
        take = per_dec + (n_dec - per_dec * len(DECISION_KEEP) if i == 0 else 0)
        parts.append(_weighted_sample(sub, take, None, rng))
    dec_sample = pd.concat(parts, ignore_index=True).copy()
    dec_sample["half"] = "decisions"
    dec_sample["product_name_original"] = dec_sample["product_name"]
    dec_sample["channel"] = np.nan
    dec_sample["price"] = np.nan
    dec_sample["input_hash"] = np.nan
    dec_sample["dedup_cluster_id"] = np.nan

    # ---- unscoped half ----
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
    unscoped = (
        pi[~pi["norm_key"].isin(owned_keys)]
        .drop_duplicates("norm_key")
        .reset_index(drop=True)
    )
    unscoped["script"] = unscoped["product_name_original"].map(script_of)
    unscoped["division"] = unscoped["declared_coicop_codes"].map(_division)
    unscoped["sampling_stratum"] = (
        unscoped["country"] + "|" + unscoped["script"] + "|" + unscoped["division"]
    )

    mult = np.ones(len(unscoped))
    mult = np.where(
        unscoped["script"].isin(OVERSAMPLE_SCRIPTS), mult * SCRIPT_MULT, mult
    )
    mult = np.where(
        ~unscoped["division"].isin(green_divs), mult * DIV_ABSENT_MULT, mult
    )
    n_uns = target - n_dec
    # oversample the draw so we can drop alias-token contaminated rows and still hit target
    draw = min(len(unscoped), int(n_uns * 1.3))
    pool = _weighted_sample(
        unscoped, draw, pd.Series(mult, index=unscoped.index), rng
    ).copy()
    tok_owned = pool["norm_key"].map(lambda k: bool(set(k.split()) & alias_tokens))
    pool = pool[~tok_owned]
    uns_sample = pool.head(n_uns).copy()
    uns_sample["half"] = "unscoped"
    # products.parquet is a stale dedup snapshot (0% input_hash overlap with the
    # current products_input), so dedup cluster ids are unavailable; W2.1 relies
    # on norm_key disjointness (every gold norm_key is recorded in the manifest).
    uns_sample["dedup_cluster_id"] = np.nan

    out = pd.concat([dec_sample, uns_sample], ignore_index=True)
    out["gold_row_id"] = [f"gv5-{i:05d}" for i in range(len(out))]
    for c in KEEP_COLS:
        if c not in out.columns:
            out[c] = np.nan
    out = out[KEEP_COLS]
    out.to_parquet(CANDIDATES_PATH, index=False)

    # ---- batch CSVs (<=150 rows) ----
    for old in BATCH_DIR.glob("gold_v5_batch_*.csv"):
        old.unlink()
    batch_cols = [
        "gold_row_id",
        "product_name_original",
        "country",
        "source",
        "channel",
        "category",
        "declared_coicop_codes",
        "price",
    ]
    for b, start in enumerate(range(0, len(out), 150)):
        out.iloc[start : start + 150][batch_cols].to_csv(
            BATCH_DIR / f"gold_v5_batch_{b:03d}.csv", index=False
        )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": _git_sha(),
        "seed": SEED,
        "target": target,
        "n_total": int(len(out)),
        "n_decisions": int(len(dec_sample)),
        "n_unscoped": int(len(uns_sample)),
        "ownership_definition": (
            "unscoped = norm_key not in product_decisions ledger AND no token in "
            "base_items head_alias_index (cascade ownership check)"
        ),
        "params": {
            "script_mult": SCRIPT_MULT,
            "div_absent_mult": DIV_ABSENT_MULT,
            "oversample_scripts": sorted(OVERSAMPLE_SCRIPTS),
        },
        "green_divisions": sorted(green_divs),
        "composition": {
            "by_half": out["half"].value_counts().to_dict(),
            "by_script": out["script"].value_counts().to_dict(),
            "by_division": out["division"].value_counts().to_dict(),
            "decisions_by_decision": dec_sample["decision"].value_counts().to_dict(),
        },
        "cluster_disjoint": {
            "mechanism": "norm_key (products.parquet stale: 0% input_hash overlap; dedup cluster ids unavailable)",
            "norm_keys": sorted(out["norm_key"].dropna().unique().tolist()),
            "dedup_cluster_ids": sorted(
                out["dedup_cluster_id"].dropna().unique().tolist()
            ),
        },
        "n_batches": (len(out) + 149) // 150,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=3000)
    args = ap.parse_args()
    out = build(args.target)
    print(f"gold v5 candidates: {len(out)} rows -> {CANDIDATES_PATH}")
    print(
        f"  decisions={int((out['half'] == 'decisions').sum())} unscoped={int((out['half'] == 'unscoped').sum())}"
    )
    print(f"  scripts: {out['script'].value_counts().to_dict()}")
    print(f"  batches -> {BATCH_DIR} ({(len(out) + 149) // 150} files)")


if __name__ == "__main__":
    main()
