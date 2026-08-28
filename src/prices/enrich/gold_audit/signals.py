"""Assemble one suspicion-feature row per gold row.

Five signal families, joined on ``gold_row_id``:

1. **OOF** — what a head trained on the rest of the gold says (``oof.py``)
2. **Neighborhood** — whether the local embedding neighbourhood agrees
   (``neighbors.py``)
3. **Original provenance** — how much the original labelers argued
   (``disagreement_type``, ``adjudicator_match``, ``confidence``, ``label_source``)
4. **Near-duplicate conflict** — near-identical product names carrying different
   gold codes; at most one of them can be right
5. **Confusion pair** — membership in a (gold, predicted) cell that the head
   gets wrong *confidently*, which is where a systematic convention error shows
   up rather than a one-off slip

Five is a deliberate cap. Adding more features before ``experiment.py`` reports
whether any of them carry signal would be tuning against noise.

This module joins and derives only. It assigns no weights and makes no ranking
decision — that is ``score.py``, kept separate so the weighting can change
without re-deriving the features.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from prices.enrich.classifier.dataset import _load_gold
from prices.enrich.gold_audit import (
    SIGNALS_FILE,
    ensure_run_dir,
    neighbors,
    oof,
    run_dir,
)

# A (gold, predicted) cell counts as a confusion pair once it recurs this often
# among high-confidence OOF errors. Below that it reads as noise.
CONFUSION_MIN_COUNT = 5
CONFUSION_CONF_FLOOR = 0.80

_NON_ALNUM = re.compile(r"[^0-9a-z　-鿿가-힯]+")


def _dupe_key(name: str) -> str:
    """Collapse a product name to a coarse identity key.

    Deliberately *not* ``normalize.clean_text``: that strips pack sizes and
    resolves brand aliases, which would merge genuinely different SKUs (a 200 g
    and a 1 kg pack) into one key and manufacture conflicts that are not label
    errors. Casefolding and punctuation removal is the most collapsing this can
    do while a collision still implies the same product."""
    s = unicodedata.normalize("NFKC", str(name)).casefold()
    return _NON_ALNUM.sub(" ", s).strip()


def _dupe_conflict(gold: pd.DataFrame) -> pd.DataFrame:
    """Flag rows whose dupe-key twins do not all carry the same gold code."""
    key = gold["product_name"].map(_dupe_key)
    codes_per_key = gold.groupby(key)["code"].nunique()
    conflicted = set(codes_per_key[codes_per_key > 1].index)
    return pd.DataFrame(
        {
            "gold_row_id": gold["gold_row_id"],
            "dupe_key": key,
            "dupe_conflict": key.isin(conflicted),
        }
    )


def _confusion_pairs(df: pd.DataFrame) -> set[tuple[str, str]]:
    """(gold, predicted) cells that recur among high-confidence OOF errors."""
    errs = df[
        (df["oof_status"] == oof.STATUS_OK)
        & (df["oof_correct"] == False)  # noqa: E712 — object dtype, `is False` fails
        & (df["oof_conf"] >= CONFUSION_CONF_FLOOR)
    ]
    if errs.empty:
        return set()
    counts = errs.groupby(["code", "oof_pred"]).size()
    return set(counts[counts >= CONFUSION_MIN_COUNT].index)


PROVENANCE_COLS = [
    "label_source",
    "disagreement_type",
    "adjudicator_match",
    "confidence",
]


def build(run_id: str) -> dict:
    """Join OOF + neighbourhood + provenance + duplicates into ``signals.parquet``."""
    gold = _load_gold().reset_index(drop=True)
    keep = ["gold_row_id", "product_name", "code", "division", "country", "verdict"]
    base = gold[[c for c in keep + PROVENANCE_COLS if c in gold.columns]].copy()

    base = base.merge(
        oof.load(run_id).drop(columns=["product_name", "code", "division"]),
        on="gold_row_id",
        how="left",
    )
    base = base.merge(neighbors.load(run_id), on="gold_row_id", how="left")
    base = base.merge(_dupe_conflict(gold), on="gold_row_id", how="left")

    pairs = _confusion_pairs(base)
    base["confusion_pair"] = [
        (c, p) in pairs for c, p in zip(base["code"], base["oof_pred"])
    ]

    # The two headline derived flags the experiment and the scorer both read.
    base["oof_disagrees"] = (base["oof_status"] == oof.STATUS_OK) & (
        base["oof_correct"] == False  # noqa: E712
    )
    base["oof_confidently_disagrees"] = base["oof_disagrees"] & (
        base["oof_conf"] >= CONFUSION_CONF_FLOOR
    )

    base.to_parquet(ensure_run_dir(run_id) / SIGNALS_FILE, index=False)

    return {
        "run_id": run_id,
        "n_rows": int(len(base)),
        "n_oof_scored": int((base["oof_status"] == oof.STATUS_OK).sum()),
        "n_oof_disagrees": int(base["oof_disagrees"].sum()),
        "n_neighbor_disagrees": int(
            base["neighbor_disagrees"].astype("boolean").fillna(False).sum()
        ),
        "n_dupe_conflict": int(
            base["dupe_conflict"].astype("boolean").fillna(False).sum()
        ),
        "n_confusion_pair": int(base["confusion_pair"].sum()),
        "n_confusion_cells": len(pairs),
    }


def load(run_id: str) -> pd.DataFrame:
    return pd.read_parquet(run_dir(run_id) / SIGNALS_FILE)
