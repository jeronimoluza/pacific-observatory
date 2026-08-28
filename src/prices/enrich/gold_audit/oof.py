"""Out-of-fold predictions for every gold row, division by division.

The production head trains on one division at a time, so a single fit leaves
~26k of the 50k gold rows with no model that has ever seen them. The audit needs
"what would a model trained on the rest of the gold say about this row?" for as
much of the corpus as possible, so this module fits a throwaway head per
division and records the out-of-fold answer.

Not every row gets one. A leaf below ``MIN_SUPPORT`` cannot be cross-validated,
and a division whose surviving leaf count drops below two has no classification
problem left. Those rows are kept in the output with an ``oof_status`` saying
why they are missing, so downstream reports state "OOF available on N of 50,126"
instead of quietly shrinking the denominator.

The throwaway heads are never persisted or blessed — only their predictions are.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prices.enrich import embedding
from prices.enrich.classifier import train
from prices.enrich.classifier.dataset import MIN_SUPPORT, _load_gold
from prices.enrich.gold_audit import OOF_FILE, ensure_run_dir

# A division needs at least two learnable leaves before "predict the leaf" is a
# question, and enough rows to survive a 5-way stratified split.
MIN_LEAVES = 2

STATUS_OK = "ok"
STATUS_NOT_LEAF = "not_leaf_verdict"
STATUS_THIN_LEAF = "leaf_below_min_support"
STATUS_NO_HEAD = "no_head"


def _eligible(gold: pd.DataFrame, min_support: int) -> pd.Series:
    """Per-row status before any fitting: which rows a head could even score."""
    status = pd.Series(STATUS_OK, index=gold.index, dtype=object)
    status[gold["verdict"] != "leaf"] = STATUS_NOT_LEAF

    leafish = status == STATUS_OK
    counts = gold.loc[leafish, "code"].value_counts()
    thin = set(counts[counts < min_support].index)
    status[leafish & gold["code"].isin(thin)] = STATUS_THIN_LEAF
    return status


def compute(
    run_id: str,
    divisions: list[str] | None = None,
    min_support: int = MIN_SUPPORT,
) -> dict:
    """Fit a throwaway head per division and write ``oof.parquet`` for the run.

    Returns a summary counting, per division, how many rows got an OOF
    prediction and how many did not."""
    gold = _load_gold().reset_index(drop=True)
    gold["oof_status"] = _eligible(gold, min_support)
    gold["oof_pred"] = pd.Series([None] * len(gold), dtype=object)
    gold["oof_conf"] = np.nan

    wanted = divisions or sorted(gold["division"].dropna().unique())
    per_division: dict[str, dict] = {}

    # Embed the whole gold set once, then slice per division. `embed_names`
    # reads ~1.7 GB of block cache and rebuilds a 50k-entry dict on every call,
    # and rewrites the cache whenever a name is missing — calling it inside the
    # division loop would pay both costs thirteen times over.
    x_all = embedding.embed_names(gold["product_name"].astype(str).tolist())

    for div in wanted:
        rows = gold.index[(gold["division"] == div) & (gold["oof_status"] == STATUS_OK)]
        codes = gold.loc[rows, "code"].to_numpy()
        n_leaves = len(set(codes))

        if n_leaves < MIN_LEAVES:
            gold.loc[rows, "oof_status"] = STATUS_NO_HEAD
            per_division[div] = {
                "n_rows": int(len(rows)),
                "n_scored": 0,
                "n_leaves": n_leaves,
            }
            continue

        pred, conf = train.cross_val_oof(x_all[rows.to_numpy()], codes)
        gold.loc[rows, "oof_pred"] = pred.astype(str)
        gold.loc[rows, "oof_conf"] = conf
        per_division[div] = {
            "n_rows": int(len(rows)),
            "n_scored": int(len(rows)),
            "n_leaves": n_leaves,
        }

    out = gold[
        [
            "gold_row_id",
            "product_name",
            "code",
            "division",
            "oof_pred",
            "oof_conf",
            "oof_status",
        ]
    ].copy()
    out["oof_correct"] = np.where(
        out["oof_status"] == STATUS_OK, out["oof_pred"] == out["code"], None
    )

    out.to_parquet(ensure_run_dir(run_id) / OOF_FILE, index=False)

    scored = int((out["oof_status"] == STATUS_OK).sum())
    return {
        "run_id": run_id,
        "n_gold": int(len(out)),
        "n_scored": scored,
        "n_unscored": int(len(out) - scored),
        "status_counts": out["oof_status"].value_counts().to_dict(),
        "per_division": per_division,
    }


def load(run_id: str) -> pd.DataFrame:
    from prices.enrich.gold_audit import run_dir

    return pd.read_parquet(run_dir(run_id) / OOF_FILE)
