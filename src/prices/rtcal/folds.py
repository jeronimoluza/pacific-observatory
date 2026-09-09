"""Deterministic validation folds, one family per way a cell can go missing.

Six families, because "can we predict a missing cell" has six different answers
depending on *why* it is missing. Holding out random cells would flatter the
method: a random holdout almost always leaves the same series observed in the
neighbouring month, which is the easy case.

Fold assignment uses blake2b rather than DuckDB's `hash`, so the exact partition
differs from William's. That is deliberate and harmless -- the published numbers
are aggregates over 5 folds of a 358k-cell frame, and any balanced random
partition reproduces them. What must match is the *scheme*, not the seed.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from . import config


def _stable_fold(values: pd.Series, salt: str, k: int) -> np.ndarray:
    """Reproducible 1..k assignment, stable across machines and runs."""
    prefix = f"{config.FOLD_SEED}|{salt}|".encode()
    out = np.empty(len(values), dtype=int)
    cache: dict[str, int] = {}
    for i, value in enumerate(values.astype(str).to_numpy()):
        hit = cache.get(value)
        if hit is None:
            digest = hashlib.blake2b(prefix + value.encode(), digest_size=8).digest()
            hit = int.from_bytes(digest, "big") % k + 1
            cache[value] = hit
        out[i] = hit
    return out


def _greedy_balanced(df: pd.DataFrame, key: str, k: int) -> np.ndarray:
    """Largest-group-first bin packing.

    A hash split on `country` would put India and Tuvalu in the same fold by
    luck; greedy packing keeps fold sizes comparable so a per-fold metric means
    the same thing in every fold.
    """
    counts = df.groupby(key, observed=True).size().sort_values(ascending=False)
    loads = [0] * k
    assignment: dict[str, int] = {}
    for group, size in counts.items():
        target = min(range(k), key=lambda i: (loads[i], i))
        assignment[group] = target + 1
        loads[target] += int(size)
    return df[key].map(assignment).to_numpy(dtype=int)


def _time_blocks(df: pd.DataFrame, k: int) -> np.ndarray:
    """Contiguous period blocks holding roughly equal cell counts.

    Equal *cells*, not equal months: the corpus is far denser in recent years, so
    equal-month blocks would make the earliest fold a rounding error.
    """
    per_period = df.groupby("period", observed=True).size().sort_index()
    cum = per_period.cumsum()
    total = int(cum.iloc[-1])
    block = np.ceil(cum.to_numpy(dtype=float) * k / total).astype(int)
    block = np.clip(block, 1, k)
    return df["period"].map(pd.Series(block, index=per_period.index)).to_numpy(dtype=int)


def add_folds(df: pd.DataFrame, k: int | None = None) -> pd.DataFrame:
    k = k or config.K_FOLDS
    out = df.copy()
    out["fold_country_month_holdout"] = _stable_fold(
        out["country"].astype(str) + "|" + out["period"].astype(str), "country_month", k
    )
    out["fold_product_month_holdout"] = _stable_fold(
        out["product_unit_id"].astype(str) + "|" + out["period"].astype(str), "product_month", k
    )
    out["fold_series_holdout"] = _stable_fold(out["series_id"], "series", k)
    out["fold_country_holdout"] = _greedy_balanced(out, "country", k)
    out["fold_product_unit_holdout"] = _greedy_balanced(out, "product_unit_id", k)
    out["fold_time_block"] = _time_blocks(out, k)
    return out


def split_masks(df: pd.DataFrame, scheme: str, fold: int):
    """Train/val masks for one (scheme, fold) unit.

    ``fold_time_block`` is special: training is everything strictly BEFORE the
    block starts, so the fold measures genuine forecasting rather than
    interpolation with a gap in the middle.
    """
    if scheme == "fold_time_block":
        val_mask = df[scheme].to_numpy() == fold
        if not val_mask.any():
            return None
        cutoff = int(df.loc[val_mask, "period_index"].min())
        train_mask = df["period_index"].to_numpy() < cutoff
        if not train_mask.any():
            return None
        return train_mask, val_mask, True
    values = df[scheme].to_numpy()
    train_mask, val_mask = values != fold, values == fold
    if not train_mask.any() or not val_mask.any():
        return None
    return train_mask, val_mask, False


SCHEME_LABELS = {
    "fold_country_month_holdout": "country_month_holdout",
    "fold_product_month_holdout": "product_month_holdout",
    "fold_series_holdout": "series_holdout",
    "fold_time_block": "time_forward_block",
    "fold_country_holdout": "country_holdout",
    "fold_product_unit_holdout": "product_unit_holdout",
}

# Which prediction each fold family is judging. Normal gaps are judged on the
# relative-temporal predictor; forward and cold-start gaps on the context
# ensemble, which is what the package selects for those roles.
SCHEME_CANDIDATE = {
    "fold_country_month_holdout": "relative_decomp_temporal",
    "fold_product_month_holdout": "relative_decomp_temporal",
    "fold_series_holdout": "ensemble_context",
    "fold_time_block": "ensemble_context",
    "fold_country_holdout": "ensemble_context",
    "fold_product_unit_holdout": "ensemble_context",
}
