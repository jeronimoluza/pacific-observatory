"""Load the cell matrix and derive every identifier the method needs.

The input is ``global_prices_unit_value_summary.parquet``, which `prices build`
already writes at exactly the grain RT-CAL wants: one row per
``(period, country, coicop_code, standard_unit)`` carrying a median USD unit
value and a trusted-observation count.

Two things here are easy to get wrong and both are load-bearing:

* ``period_index`` is 1-based over the distinct periods *present in the frame*,
  not a calendar offset. ``low_rank_svd`` indexes a dense matrix with
  ``period_index - 1`` and sizes it from ``period_index.max()``, so a 0-based or
  sparse index silently shifts every prediction by one month.
* Training rows are ``n_trusted > 0``, NOT ``cell_status == "usable"``. Usable
  means ``n_trusted >= 5`` and covers only a quarter of the matrix; the method
  was validated on the looser rule and the thin cells are most of the signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

REQUIRED_CELL_COLS = (
    "period",
    "country",
    "coicop_code",
    "standard_unit",
    "median_unit_value_usd",
    "n_trusted",
    "cell_status",
)

REQUIRED_CONTEXT_COLS = (
    "country_region_id",
    "country_income_id",
    "country_latitude",
    "country_longitude",
)


class ContractError(ValueError):
    """The input frame does not satisfy ``DATA_CONTRACT.md``."""


def validate_contract(df: pd.DataFrame) -> None:
    """Hard schema gate. Fail before fitting, never halfway through."""
    missing = [c for c in REQUIRED_CELL_COLS if c not in df.columns]
    if missing:
        raise ContractError(f"unit-value summary is missing required columns: {missing}")
    for col in ("period", "country", "coicop_code", "standard_unit"):
        if df[col].isna().any():
            raise ContractError(f"{col} carries nulls; coordinates must be complete")
    bad_period = ~df["period"].astype(str).str.fullmatch(r"\d{4}-\d{2}")
    if bad_period.any():
        sample = df.loc[bad_period, "period"].astype(str).unique()[:5].tolist()
        raise ContractError(f"period must be YYYY-MM strings; saw {sample}")


def period_index_map(periods) -> dict[str, int]:
    """1-based index over sorted distinct periods (see the module docstring)."""
    return {p: i + 1 for i, p in enumerate(sorted(set(periods)))}


def load_cells(path=None) -> pd.DataFrame:
    path = path or config.UNIT_VALUE_SUMMARY_PARQUET
    df = pd.read_parquet(path)
    validate_contract(df)
    df = df.copy()
    df["period"] = df["period"].astype(str)
    for col in ("country", "coicop_code", "standard_unit"):
        df[col] = df[col].astype(str)
    df["period_index"] = df["period"].map(period_index_map(df["period"])).astype(int)
    return add_core_ids(df)


def add_core_ids(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    country = out["country"].astype(str)
    code = out["coicop_code"].astype(str)
    unit = out["standard_unit"].astype(str)
    out["series_id"] = country + "|" + code + "|" + unit
    out["country_product_id"] = country + "|" + code
    out["product_unit_id"] = code + "|" + unit
    return out


def observed_cells(df: pd.DataFrame) -> pd.DataFrame:
    """Cells eligible to train on, before pruning.

    ``n_trusted > 0`` with a finite positive USD value -- the DATA_CONTRACT rule,
    not the stricter ``cell_status`` one.
    """
    usd = pd.to_numeric(df["median_unit_value_usd"], errors="coerce")
    keep = (df["n_trusted"] > 0) & np.isfinite(usd) & (usd > 0)
    out = df.loc[keep].copy()
    out["log_median_unit_value_usd"] = np.log(
        pd.to_numeric(out["median_unit_value_usd"], errors="coerce").to_numpy(dtype=float)
    )
    return out.reset_index(drop=True)


def load_country_context(path=None) -> pd.DataFrame:
    """The frozen country table.

    Frozen on purpose: ``DATA_CONTRACT.md`` forbids calling an external API from
    a scheduled run, and a region id that changes underneath a fitted model
    changes the model.
    """
    path = path or config.COUNTRY_CONTEXT_CSV
    meta = pd.read_csv(path)
    if "country" not in meta.columns:
        raise ContractError("country context table must be keyed on `country`")
    missing = [c for c in REQUIRED_CONTEXT_COLS if c not in meta.columns]
    if missing:
        raise ContractError(f"country context is missing {missing}")
    keep = ["country", *REQUIRED_CONTEXT_COLS]
    return meta[keep].drop_duplicates("country").reset_index(drop=True)


def attach_country_context(df: pd.DataFrame, meta: pd.DataFrame | None = None):
    """Left-join context; unmatched countries get UNK/0.0 and are reported."""
    meta = load_country_context() if meta is None else meta
    out = df.merge(meta, on="country", how="left", validate="many_to_one")
    unmatched = sorted(out.loc[out["country_region_id"].isna(), "country"].unique().tolist())
    out["country_region_id"] = out["country_region_id"].fillna("UNK").astype(str)
    out["country_income_id"] = out["country_income_id"].fillna("UNK").astype(str)
    out["country_latitude"] = pd.to_numeric(out["country_latitude"], errors="coerce").fillna(0.0)
    out["country_longitude"] = pd.to_numeric(out["country_longitude"], errors="coerce").fillna(0.0)
    return out, unmatched


def _coicop_prefix(code: str, depth: int) -> str:
    parts = str(code).split(".")
    if not parts or parts == [""]:
        return "missing"
    return ".".join(parts[: min(depth, len(parts))])


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Every interaction key the predictors and the pruner index on.

    Built once, up front, because the fold runner slices this frame rather than
    rebuilding it -- deriving inside a fold would make each fold pay for it and
    would let a fold-local category set drift from the global one.
    """
    out = df.copy()
    out["y"] = out["log_median_unit_value_usd"].astype(float)

    country = out["country"].astype(str)
    code = out["coicop_code"].astype(str)
    unit = out["standard_unit"].astype(str)
    period = out["period"].astype(str)
    region = out["country_region_id"].astype(str)
    income = out["country_income_id"].astype(str)
    product_unit = out["product_unit_id"].astype(str)

    out["country_period_id"] = country + "|" + period
    out["product_unit_period_id"] = product_unit + "|" + period
    out["coicop_period_id"] = code + "|" + period
    out["country_product_period_id"] = out["country_product_id"].astype(str) + "|" + period
    out["country_product_unit_period_id"] = out["series_id"].astype(str) + "|" + period
    out["unit_period_id"] = unit + "|" + period

    for depth in range(1, 5):
        col = f"coicop_l{depth}"
        out[col] = code.map(lambda v, d=depth: _coicop_prefix(v, d))
        level = out[col].astype(str)
        out[f"{col}_unit"] = level + "|" + unit
        out[f"{col}_period"] = level + "|" + period
        out[f"{col}_unit_period"] = level + "|" + unit + "|" + period
        out[f"country_{col}"] = country + "|" + level
        out[f"country_{col}_unit"] = country + "|" + level + "|" + unit
        out[f"country_{col}_period"] = country + "|" + level + "|" + period
        out[f"country_{col}_unit_period"] = country + "|" + level + "|" + unit + "|" + period
        out[f"region_{col}_unit"] = region + "|" + level + "|" + unit
        out[f"region_{col}_unit_period"] = region + "|" + level + "|" + unit + "|" + period

    out["region_product_unit_id"] = region + "|" + product_unit
    out["region_product_unit_period_id"] = region + "|" + product_unit + "|" + period
    out["region_period_id"] = region + "|" + period
    out["region_unit_period_id"] = region + "|" + unit + "|" + period
    out["income_product_unit_id"] = income + "|" + product_unit
    out["income_period_id"] = income + "|" + period

    lat = out["country_latitude"].to_numpy(dtype=float)
    lon = out["country_longitude"].to_numpy(dtype=float)
    out["country_geo_known"] = (
        np.isfinite(lat) & np.isfinite(lon) & ((lat != 0.0) | (lon != 0.0))
    ).astype(int)
    out["country_latitude_abs"] = np.abs(lat)
    out["country_latitude_sin"] = np.sin(np.deg2rad(lat))
    out["country_longitude_sin"] = np.sin(np.deg2rad(lon))
    out["country_longitude_cos"] = np.cos(np.deg2rad(lon))
    return out


def prepare_observed(path=None, context=None):
    """Summary parquet -> pruning-ready observed frame. Returns (frame, unmatched)."""
    cells = load_cells(path)
    obs = observed_cells(cells)
    obs, unmatched = attach_country_context(obs, context)
    return add_derived_features(obs), unmatched
