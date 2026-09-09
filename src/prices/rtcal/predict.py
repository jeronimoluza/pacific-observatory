"""The RT-CAL predictor bank.

Ported from William's fold runner. Two design points are worth stating because
they constrain how this may be parallelized:

* ``additive_fe`` is backfitting. Iteration *k* reads the running prediction
  that iteration *k-1* wrote, and within an iteration each key reads what the
  previous key just added. It is sequential by construction.
* Every predictor is a pure function of ``(train, val)``. Nothing caches, nothing
  mutates shared state. That is what makes fold-level parallelism safe -- and it
  is also why sharding *training data* is not: each predictor pools across the
  whole train frame on purpose, so a shard changes the fit rather than splitting
  it.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import config

try:  # pragma: no cover - environment probe
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder

    SKLEARN_ERROR = None
except Exception as exc:  # pragma: no cover
    SKLEARN_ERROR = exc


def map_series(values, mapping):
    return values.map(mapping).to_numpy(dtype=float, na_value=np.nan)


def grouped_stat(train, key, stat="median"):
    grouped = train.groupby(key, sort=False, observed=True)["y"]
    if stat == "median":
        return grouped.median()
    if stat == "mean":
        return grouped.mean()
    if stat == "count":
        return grouped.size()
    raise ValueError(stat)


def fallback_group_predict(train, val, levels, stat="median"):
    """Walk levels most-specific first; the first level with a value wins."""
    pred = np.full(len(val), np.nan, dtype=float)
    support = np.zeros(len(val), dtype=float)
    level_hit = np.full(len(val), -1, dtype=int)
    for i, key in enumerate(levels):
        mapping = grouped_stat(train, key, stat=stat)
        counts = grouped_stat(train, key, stat="count")
        candidate = map_series(val[key], mapping)
        use = (~np.isfinite(pred)) & np.isfinite(candidate)
        if use.any():
            pred[use] = candidate[use]
            support[use] = np.nan_to_num(map_series(val.loc[use, key], counts), nan=0.0)
            level_hit[use] = i
    missing = ~np.isfinite(pred)
    if missing.any():
        pred[missing] = float(train["y"].median() if stat == "median" else train["y"].mean())
        support[missing] = float(len(train))
        level_hit[missing] = len(levels)
    return pred, support, level_hit


def temporal_interpolate(train, val, past_only=False):
    """Linear interpolation along a series, flat-extrapolated at both ends.

    ``past_only=True`` is the forward-time variant: it carries the last prior
    observation forward and returns NaN when there is none, so a forward-gap
    prediction can never see an observation from its own future.
    """
    pred = pd.Series(np.nan, index=val.index, dtype=float)
    train_sorted = train[["series_id", "period_index", "y"]].sort_values(["series_id", "period_index"])
    grouped = {
        series: (
            group["period_index"].to_numpy(dtype=float),
            group["y"].to_numpy(dtype=float),
        )
        for series, group in train_sorted.groupby("series_id", sort=False)
    }
    for series, sub in val.groupby("series_id", sort=False):
        item = grouped.get(series)
        if item is None:
            continue
        xp, fp = item
        x = sub["period_index"].to_numpy(dtype=float)
        if past_only:
            idx = np.searchsorted(xp, x, side="left") - 1
            ok = idx >= 0
            vals = np.full(len(x), np.nan, dtype=float)
            vals[ok] = fp[idx[ok]]
        else:
            vals = np.interp(x, xp, fp, left=fp[0], right=fp[-1])
        pred.loc[sub.index] = vals
    return pred.to_numpy(dtype=float)


def additive_fe(train, val, keys, lambdas, iterations, center="mean", learning_rate=0.55, update_clip=1.0):
    """Shrunken additive fixed effects by backfitting. Returns (train, val) preds."""
    mu = float(train["y"].mean() if center == "mean" else train["y"].median())
    effects = {key: pd.Series(dtype=float) for key in keys}
    train_y = train["y"].to_numpy(dtype=float)
    train_pred = np.full(len(train), mu, dtype=float)

    for _ in range(iterations):
        for key in keys:
            residual = train_y - train_pred
            tmp = pd.DataFrame({"key": train[key].to_numpy(), "residual": residual})
            stats = tmp.groupby("key", sort=False, observed=True)["residual"].agg(["sum", "count"])
            lam = lambdas.get(key, 10.0)
            update = learning_rate * (stats["sum"] / (stats["count"] + lam))
            update = update.clip(-update_clip, update_clip)
            effects[key] = effects[key].add(update, fill_value=0.0).clip(
                -config.BASELINE_TOTAL_CLIP, config.BASELINE_TOTAL_CLIP
            )
            train_pred += train[key].map(update).fillna(0.0).to_numpy(dtype=float)

    val_pred = np.full(len(val), mu, dtype=float)
    for key in keys:
        val_pred += val[key].map(effects[key]).fillna(0.0).to_numpy(dtype=float)
    return train_pred, val_pred


def relative_baseline_fit_predict(train, val):
    """The shared relative-price surface every residual model sits on top of."""
    return additive_fe(
        train,
        val,
        config.RELATIVE_BASELINE_KEYS,
        config.RELATIVE_BASELINE_LAMBDAS,
        iterations=config.BASELINE_ITERATIONS,
        center="mean",
        learning_rate=config.BASELINE_LEARNING_RATE,
        update_clip=config.BASELINE_UPDATE_CLIP,
    )


def additive_fe_series_predict(train, val):
    _, pred = additive_fe(
        train,
        val,
        ["country", "product_unit_id", "coicop_code", "standard_unit", "period", "series_id", "country_product_id"],
        {
            "country": 30.0,
            "product_unit_id": 25.0,
            "coicop_code": 30.0,
            "standard_unit": 30.0,
            "period": 25.0,
            "series_id": 8.0,
            "country_product_id": 12.0,
        },
        iterations=8,
    )
    return pred


def weighted_group_pool_predict(train, val, levels, global_value):
    numerator = np.zeros(len(val), dtype=float)
    denominator = np.zeros(len(val), dtype=float)
    for key, base_weight, shrinkage in levels:
        stats = train.groupby(key, sort=False, observed=True)["y"].agg(["median", "count"])
        pred = map_series(val[key], stats["median"])
        counts = map_series(val[key], stats["count"])
        ok = np.isfinite(pred) & np.isfinite(counts) & (counts > 0)
        if not ok.any():
            continue
        weights = base_weight * (counts[ok] / (counts[ok] + shrinkage))
        numerator[ok] += weights * pred[ok]
        denominator[ok] += weights
    weak = denominator <= 0
    out = np.empty(len(val), dtype=float)
    out[~weak] = numerator[~weak] / denominator[~weak]
    out[weak] = global_value
    return out


COICOP_POOL_LEVELS = [
    ("series_id", 4.5, 3.0),
    ("country_product_id", 3.5, 5.0),
    ("country_coicop_l4_unit", 3.0, 8.0),
    ("country_coicop_l3_unit", 2.4, 12.0),
    ("country_coicop_l2_unit", 1.8, 18.0),
    ("country_coicop_l1_unit", 1.2, 30.0),
    ("product_unit_period_id", 2.8, 10.0),
    ("coicop_l4_unit_period", 2.2, 15.0),
    ("coicop_l3_unit_period", 1.8, 22.0),
    ("coicop_l2_unit_period", 1.4, 35.0),
    ("product_unit_id", 2.4, 20.0),
    ("coicop_l4_unit", 2.0, 25.0),
    ("coicop_l3_unit", 1.6, 35.0),
    ("coicop_l2_unit", 1.2, 50.0),
    ("country_period_id", 1.6, 20.0),
    ("country", 1.0, 60.0),
    ("period", 0.7, 200.0),
    ("standard_unit", 0.5, 250.0),
]


def coicop_hier_pool_predict(train, val):
    return weighted_group_pool_predict(train, val, COICOP_POOL_LEVELS, float(train["y"].median()))


_RIDGE_ONEHOT_CATS = [
    "country",
    "product_unit_id",
    "coicop_code",
    "standard_unit",
    "period",
    "series_id",
    "country_period_id",
    "product_unit_period_id",
    "country_product_id",
]

_RIDGE_CONTEXT_CATS = [
    "product_unit_id",
    "coicop_code",
    "coicop_l1_unit",
    "coicop_l2_unit",
    "coicop_l3_unit",
    "coicop_l4_unit",
    "standard_unit",
    "period",
    "country_region_id",
    "country_income_id",
    "region_product_unit_id",
    "region_product_unit_period_id",
    "region_period_id",
    "region_unit_period_id",
    "income_product_unit_id",
    "income_period_id",
]

_RIDGE_CONTEXT_NUM = [
    "period_index",
    "country_latitude",
    "country_longitude",
    "country_latitude_abs",
    "country_latitude_sin",
    "country_longitude_sin",
    "country_longitude_cos",
    "country_geo_known",
]


def _ridge_predict(train, val, cats, numeric, alpha):
    if SKLEARN_ERROR is not None:  # pragma: no cover
        return np.full(len(val), np.nan, dtype=float)
    transformer = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=2, sparse_output=True), cats),
            ("num", "passthrough", numeric),
        ],
        sparse_threshold=1.0,
    )
    pipe = make_pipeline(transformer, Ridge(alpha=alpha, solver="lsqr", random_state=config.SEED))
    pipe.fit(train[cats + numeric], train["y"])
    return pipe.predict(val[cats + numeric])


def ridge_onehot_predict(train, val):
    return _ridge_predict(train, val, _RIDGE_ONEHOT_CATS, ["period_index"], alpha=20.0)


def ridge_context_predict(train, val):
    return _ridge_predict(train, val, _RIDGE_CONTEXT_CATS, _RIDGE_CONTEXT_NUM, alpha=25.0)


def low_rank_svd_predict(df, train_mask, val_mask, rank=8):
    """Series x period matrix, two-way centred, truncated-SVD on the residual."""
    all_series = pd.Index(df["series_id"].unique())
    row_lookup = pd.Series(np.arange(len(all_series)), index=all_series)
    rows = df["series_id"].map(row_lookup).to_numpy(dtype=int)
    cols = df["period_index"].to_numpy(dtype=int) - 1
    n_rows = len(all_series)
    n_cols = int(df["period_index"].max())

    matrix = np.full((n_rows, n_cols), np.nan, dtype=np.float64)
    matrix[rows[train_mask], cols[train_mask]] = df.loc[train_mask, "y"].to_numpy(dtype=float)
    mu = float(np.nanmean(matrix))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        row_mean = np.nanmean(matrix, axis=1)
        col_mean = np.nanmean(matrix, axis=0)
    row_effect = np.where(np.isfinite(row_mean), row_mean - mu, 0.0)
    col_effect = np.where(np.isfinite(col_mean), col_mean - mu, 0.0)
    baseline = mu + row_effect[:, None] + col_effect[None, :]
    observed = np.isfinite(matrix)
    residual = np.zeros_like(matrix)
    residual[observed] = matrix[observed] - baseline[observed]
    u, s, vt = np.linalg.svd(residual, full_matrices=False)
    k = min(rank, len(s))
    pred_matrix = baseline + (u[:, :k] * s[:k]) @ vt[:k, :]
    return pred_matrix[rows[val_mask], cols[val_mask]]


def haversine_km(lat, lon):
    lat = np.deg2rad(lat)
    lon = np.deg2rad(lon)
    dlat = lat[None, :] - lat[:, None]
    dlon = lon[None, :] - lon[:, None]
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2.0) ** 2
    return 6371.0 * 2.0 * np.arcsin(np.sqrt(np.minimum(a, 1.0)))


def country_similarity_lookup(train, val, bandwidth_km=None):
    """Country-to-country weights: distance decay, boosted by region and income.

    This is the cross-country borrowing that makes data-sharding wrong -- a
    country with thin support is predicted partly from its neighbours.
    """
    bandwidth_km = bandwidth_km or config.SIMILARITY_BANDWIDTH_KM
    meta_cols = ["country", "country_latitude", "country_longitude", "country_region_id", "country_income_id"]
    meta = (
        pd.concat([train[meta_cols], val[meta_cols]], ignore_index=True)
        .drop_duplicates("country")
        .reset_index(drop=True)
    )
    lat = pd.to_numeric(meta["country_latitude"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    lon = pd.to_numeric(meta["country_longitude"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    similarity = np.exp(-haversine_km(lat, lon) / bandwidth_km)
    regions = meta["country_region_id"].fillna("UNK").astype(str).to_numpy()
    incomes = meta["country_income_id"].fillna("UNK").astype(str).to_numpy()
    similarity = similarity * np.where(regions[:, None] == regions[None, :], config.SIMILARITY_SAME_REGION, 1.0)
    similarity = similarity * np.where(incomes[:, None] == incomes[None, :], config.SIMILARITY_SAME_INCOME, 1.0)
    similarity = np.maximum(similarity, 1e-6)
    country_to_idx = pd.Series(np.arange(len(meta), dtype=int), index=meta["country"].astype(str))
    return country_to_idx, similarity


def weighted_similarity_residual(val, train_residual, country_to_idx, similarity, key, shrinkage, base_weight):
    pred_num = np.zeros(len(val), dtype=float)
    pred_den = np.zeros(len(val), dtype=float)
    train_country_idx = train_residual["country"].astype(str).map(country_to_idx).to_numpy(dtype=int)
    val_country_idx = val["country"].astype(str).map(country_to_idx).to_numpy(dtype=int)
    group_stats = (
        pd.DataFrame(
            {
                "key": train_residual[key].to_numpy(),
                "country_idx": train_country_idx,
                "residual": train_residual["y"].to_numpy(dtype=float),
            }
        )
        .groupby(["key", "country_idx"], observed=True, sort=False)["residual"]
        .median()
        .reset_index()
    )
    grouped = {
        group_key: (
            group["country_idx"].to_numpy(dtype=int),
            group["residual"].to_numpy(dtype=float),
        )
        for group_key, group in group_stats.groupby("key", observed=True, sort=False)
    }
    val_keys = pd.Series(val[key].to_numpy())
    for group_key, row_idx in val_keys.groupby(val_keys, observed=True, sort=False).groups.items():
        candidate = grouped.get(group_key)
        if candidate is None:
            continue
        candidate_countries, candidate_values = candidate
        out_idx = np.asarray(row_idx, dtype=int)
        weights = similarity[val_country_idx[out_idx]][:, candidate_countries]
        weight_sum = weights.sum(axis=1)
        ok = weight_sum > 0
        if not ok.any():
            continue
        support = len(candidate_countries)
        level_weight = base_weight * (support / (support + shrinkage))
        values = weights @ candidate_values / np.maximum(weight_sum, 1e-12)
        pred_num[out_idx[ok]] += level_weight * values[ok]
        pred_den[out_idx[ok]] += level_weight
    return pred_num, pred_den


SIMILARITY_LEVELS = [
    ("product_unit_period_id", 6.0, 8.0),
    ("coicop_l4_unit_period", 5.0, 10.0),
    ("coicop_l3_unit_period", 3.5, 15.0),
    ("coicop_l2_unit_period", 2.0, 25.0),
    ("product_unit_id", 2.5, 20.0),
    ("coicop_l4_unit", 2.0, 30.0),
    ("coicop_l3_unit", 1.5, 45.0),
    ("coicop_l2_unit", 1.0, 60.0),
]


def country_similarity_residual_predict(train, val, baseline=None):
    train_baseline, val_baseline = baseline if baseline is not None else relative_baseline_fit_predict(train, val)
    train_residual = train.copy()
    train_residual["y"] = train["y"].to_numpy(dtype=float) - train_baseline
    country_to_idx, similarity = country_similarity_lookup(train, val)
    numerator = np.zeros(len(val), dtype=float)
    denominator = np.zeros(len(val), dtype=float)
    for key, base_weight, shrinkage in SIMILARITY_LEVELS:
        level_num, level_den = weighted_similarity_residual(
            val, train_residual, country_to_idx, similarity, key, shrinkage=shrinkage, base_weight=base_weight
        )
        numerator += level_num
        denominator += level_den
    residual = np.divide(numerator, denominator, out=np.zeros(len(val), dtype=float), where=denominator > 0)
    return val_baseline + residual


def relative_decomp_predict(train, val, past_only=False, temporal=False, baseline=None):
    """The production predictor for normal gaps.

    Baseline surface, plus a residual taken from the cell's own series where the
    series has anything to say, and from progressively coarser pools where it
    does not. The residual is shrunk by ``support / (support + 6)`` so a residual
    resting on one observation is mostly discarded.
    """
    train_baseline, val_baseline = baseline if baseline is not None else relative_baseline_fit_predict(train, val)
    train_residual = train.copy()
    train_residual["y"] = train["y"].to_numpy(dtype=float) - train_baseline

    if temporal:
        temporal_residual = temporal_interpolate(train_residual, val, past_only=past_only)
    else:
        temporal_residual = np.full(len(val), np.nan, dtype=float)

    fallback_residual, fallback_support, _ = fallback_group_predict(
        train_residual, val, config.RESIDUAL_FALLBACK_LEVELS, stat="median"
    )
    residual = np.where(np.isfinite(temporal_residual), temporal_residual, fallback_residual)
    series_counts = grouped_stat(train, "series_id", stat="count")
    support = map_series(val["series_id"], series_counts)
    support = np.where(np.isfinite(support), support, fallback_support)
    shrink = support / (support + config.RESIDUAL_SHRINK_LAMBDA)
    shrink = np.where(np.isfinite(shrink), shrink, 0.0)
    return val_baseline + residual * shrink


_HIER_FALLBACK = ["series_id", "country_product_id", "product_unit_id", "country", "coicop_code", "standard_unit", "period"]

# The two ensembles differ only in whether country context is allowed in.
# `ensemble_structural` is not a production predictor -- its dispersion is a
# GATE FEATURE, which is why it is computed even though nothing publishes it.
STRUCTURAL_COMPONENTS = (
    "product_period_median",
    "series_median_hierarchy",
    "temporal_bidir_hierarchy",
    "temporal_past_hierarchy",
    "additive_fe_series",
    "ridge_onehot",
    "low_rank_svd_rank8",
    "coicop_hier_additive",
    "relative_decomp_residual",
    "relative_decomp_temporal",
)

CONTEXT_COMPONENTS = (
    "product_period_median",
    "series_median_hierarchy",
    "temporal_bidir_hierarchy",
    "temporal_past_hierarchy",
    "additive_fe_series",
    "ridge_onehot",
    "low_rank_svd_rank8",
    "coicop_hier_additive",
    "relative_decomp_temporal",
    "ridge_context",
    "country_similarity_residual",
)

ALL_COMPONENTS = tuple(dict.fromkeys(STRUCTURAL_COMPONENTS + CONTEXT_COMPONENTS))


def prediction_range(stack):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)


def compute_components(df, train_mask, val_mask, past_only=False):
    """Every component prediction plus the two ensembles.

    ``past_only`` propagates the forward-time rule into the temporal residual so
    a forward gap is never interpolated across its own future.
    """
    train = df.loc[train_mask].copy()
    val = df.loc[val_mask].copy()
    preds: dict[str, np.ndarray] = {}

    preds["product_period_median"], _, _ = fallback_group_predict(
        train, val, ["product_unit_period_id", "product_unit_id", "coicop_period_id", "coicop_code", "standard_unit", "period"]
    )
    preds["series_median_hierarchy"], _, _ = fallback_group_predict(train, val, _HIER_FALLBACK)

    for name, past in (("temporal_bidir_hierarchy", False), ("temporal_past_hierarchy", True)):
        temporal = temporal_interpolate(train, val, past_only=past)
        fallback, _, _ = fallback_group_predict(train, val, _HIER_FALLBACK)
        preds[name] = np.where(np.isfinite(temporal), temporal, fallback)

    preds["additive_fe_series"] = additive_fe_series_predict(train, val)
    preds["ridge_onehot"] = ridge_onehot_predict(train, val)
    preds["low_rank_svd_rank8"] = low_rank_svd_predict(df, train_mask, val_mask)

    baseline = relative_baseline_fit_predict(train, val)
    preds["coicop_hier_additive"] = baseline[1]
    preds["ridge_context"] = ridge_context_predict(train, val)
    preds["country_similarity_residual"] = country_similarity_residual_predict(train, val, baseline=baseline)
    preds["relative_decomp_residual"] = relative_decomp_predict(
        train, val, temporal=False, baseline=baseline
    )
    preds["relative_decomp_temporal"] = relative_decomp_predict(
        train, val, temporal=True, past_only=past_only, baseline=baseline
    )

    stats = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        for label, names in (("structural", STRUCTURAL_COMPONENTS), ("context", CONTEXT_COMPONENTS)):
            stack = np.vstack([preds[name] for name in names])
            preds[f"ensemble_{label}"] = np.nanmedian(stack, axis=0)
            stats[f"ensemble_{label}_sd"] = np.nanstd(stack, axis=0)
            stats[f"ensemble_{label}_range"] = prediction_range(stack)
            stats[f"ensemble_{label}_n"] = np.isfinite(stack).sum(axis=0)
    return preds, stats
