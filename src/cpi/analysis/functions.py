"""
Core data loading, normalization, and validation pipeline for CPI analysis.

This module provides the foundational functions for loading scraped supermarket
price data, validating it, and preparing it for downstream coverage and quality
analysis.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from ..price_index.utils import (
    coicop_4digit_to_3digit,
    coicop_to_2digit,
    coicop_to_1digit,
    validate_coicop_code,
)
from .coicop_utils import load_all_coicop_levels


# Required columns per README specification
REQUIRED_COLUMNS = [
    "url_hash",
    "unit_value",
    "date",
    "coicop_code",
    "country",
]

# Recommended columns for deeper coverage and debugging
RECOMMENDED_COLUMNS = [
    "source",
    "product_name",
    "product_w_cat",
    "price",
    "currency",
    "amount",
    "units",
    "coicop_title",
    "product_url",
    "product_id",
    "wayback",
]


def load_prices_csv(path: str | Path) -> pd.DataFrame:
    """
    Load price data from CSV and derive standardized columns.

    Performs:
    - Validates required columns exist
    - Coerces unit_value to numeric
    - Parses date into date_parsed
    - Derives month (YYYY-MM), year (YYYY)
    - Normalizes wayback to is_wayback boolean
    - Derives coicop_3digit from coicop_code

    Args:
        path: Path to the price data CSV file

    Returns:
        DataFrame with derived columns added

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If required columns are missing
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Price data file not found: {path}")

    df = pd.read_csv(path, encoding="utf-8")

    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Coerce unit_value to numeric
    df["unit_value"] = pd.to_numeric(df["unit_value"], errors="coerce")

    # Parse date into date_parsed
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")

    # Derive month (YYYY-MM) and year (YYYY)
    df["month"] = df["date_parsed"].dt.to_period("M").astype(str)
    df["year"] = df["date_parsed"].dt.year.astype("Int64").astype(str)

    # Normalize wayback to is_wayback boolean
    if "wayback" in df.columns:
        df["is_wayback"] = df["wayback"].fillna(0).astype(bool)
    else:
        df["is_wayback"] = False

    # Derive coicop_3digit, coicop_2digit, and coicop_1digit from coicop_code
    df["coicop_3digit"] = df["coicop_code"].apply(coicop_4digit_to_3digit)
    df["coicop_2digit"] = df["coicop_code"].apply(coicop_to_2digit)
    df["coicop_1digit"] = df["coicop_code"].apply(coicop_to_1digit)

    return df


def validate_prices(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Validate price data and compute validation statistics.

    Validation checks:
    - unit_value: must be numeric and > 0
    - date_parsed: must not be NaT
    - coicop_code: must pass validate_coicop_code

    Args:
        df: DataFrame from load_prices_csv

    Returns:
        Tuple of (df_valid, stats) where:
        - df_valid: DataFrame with only valid rows
        - stats: Dictionary with validation statistics
    """
    stats = {
        "total_rows": len(df),
        "invalid_unit_value": 0,
        "invalid_date": 0,
        "invalid_coicop": 0,
        "valid_rows": 0,
    }

    # Invalid unit_value: NaN or <= 0
    invalid_unit_value = df["unit_value"].isna() | (df["unit_value"] <= 0)
    stats["invalid_unit_value"] = int(invalid_unit_value.sum())

    # Invalid dates: NaT
    invalid_date = df["date_parsed"].isna()
    stats["invalid_date"] = int(invalid_date.sum())

    # Invalid COICOP codes
    invalid_coicop = ~df["coicop_code"].apply(validate_coicop_code)
    stats["invalid_coicop"] = int(invalid_coicop.sum())

    # Filter to valid rows
    valid_mask = ~invalid_unit_value & ~invalid_date & ~invalid_coicop
    df_valid = df[valid_mask].copy()
    stats["valid_rows"] = len(df_valid)

    return df_valid, stats


def build_summary(df_valid: pd.DataFrame, validation_stats: Dict) -> Dict:
    """
    Build dataset-level summary statistics.

    Args:
        df_valid: Validated DataFrame from validate_prices
        validation_stats: Stats dictionary from validate_prices

    Returns:
        Dictionary with summary statistics including:
        - n_obs, n_items, n_countries, n_sources
        - date range (min_date, max_date)
        - n_months
        - n_coicop_3digit, n_coicop_4digit
        - validation_stats (attached)
    """
    summary = {
        "n_obs": len(df_valid),
        "n_items": df_valid["url_hash"].nunique(),
        "n_countries": df_valid["country"].nunique(),
        "min_date": (
            str(df_valid["date_parsed"].min().date()) if len(df_valid) > 0 else None
        ),
        "max_date": (
            str(df_valid["date_parsed"].max().date()) if len(df_valid) > 0 else None
        ),
        "n_months": df_valid["month"].nunique(),
        "n_coicop_2digit": df_valid["coicop_2digit"].nunique(),
        "n_coicop_3digit": df_valid["coicop_3digit"].nunique(),
        "n_coicop_4digit": df_valid["coicop_code"].nunique(),
    }

    # n_sources if source column exists
    if "source" in df_valid.columns:
        summary["n_sources"] = df_valid["source"].nunique()
    else:
        summary["n_sources"] = None

    # Attach validation stats
    summary["validation_stats"] = validation_stats

    return summary


# =============================================================================
# COVERAGE TABLES
# =============================================================================

# Columns to check for missingness
MISSINGNESS_COLS = [
    "amount",
    "units",
    "product_url",
    "product_id",
    "coicop_title",
    "price",
]


def coverage_table(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    """
    Compute coverage statistics grouped by specified columns.

    Args:
        df: Validated DataFrame
        group_cols: List of columns to group by

    Returns:
        DataFrame with n_items, n_obs, share_items, share_obs
    """
    total_items = df["url_hash"].nunique()
    total_obs = len(df)

    result = df.groupby(group_cols, as_index=False).agg(
        n_items=("url_hash", "nunique"),
        n_obs=("url_hash", "size"),
    )

    result["share_items"] = result["n_items"] / total_items if total_items > 0 else 0
    result["share_obs"] = result["n_obs"] / total_obs if total_obs > 0 else 0

    # Sort descending by n_items
    result = result.sort_values("n_items", ascending=False).reset_index(drop=True)

    return result


# Cache for COICOP mappings to avoid reloading
_COICOP_MAPPINGS_CACHE = None


def _get_coicop_mappings() -> Dict[int, Dict[str, str]]:
    """Get cached COICOP mappings for all levels."""
    global _COICOP_MAPPINGS_CACHE
    if _COICOP_MAPPINGS_CACHE is None:
        _COICOP_MAPPINGS_CACHE = load_all_coicop_levels()
    return _COICOP_MAPPINGS_CACHE


def _get_coicop_title_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """Get unique coicop_code to coicop_title mapping if available."""
    if "coicop_title" not in df.columns:
        return None
    return df[["coicop_code", "coicop_title"]].drop_duplicates()


def _add_coicop_titles_to_result(
    result: pd.DataFrame, code_column: str, level: int
) -> pd.DataFrame:
    """Add COICOP titles to result DataFrame based on code column and level."""
    if code_column not in result.columns:
        return result

    mappings = _get_coicop_mappings()
    if level not in mappings:
        return result

    result = result.copy()
    result["coicop_title"] = result[code_column].map(mappings[level])
    return result


def coverage_coicop_l1_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by COICOP level 1 (overall)."""
    result = coverage_table(df, ["coicop_1digit"])
    result = _add_coicop_titles_to_result(result, "coicop_1digit", level=1)
    return result


def coverage_coicop_l2_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by COICOP level 2 (overall)."""
    result = coverage_table(df, ["coicop_2digit"])
    result = _add_coicop_titles_to_result(result, "coicop_2digit", level=2)
    return result


def coverage_coicop_l3_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by COICOP level 3 (overall)."""
    result = coverage_table(df, ["coicop_3digit"])
    result = _add_coicop_titles_to_result(result, "coicop_3digit", level=3)
    return result


def coverage_coicop_l4_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by COICOP level 4 (overall)."""
    result = coverage_table(df, ["coicop_code"])
    result = _add_coicop_titles_to_result(result, "coicop_code", level=4)
    return result


def coverage_coicop_l1_country(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x COICOP level 1."""
    result = coverage_table(df, ["country", "coicop_1digit"])
    result = _add_coicop_titles_to_result(result, "coicop_1digit", level=1)
    return result


def coverage_coicop_l2_country(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x COICOP level 2."""
    result = coverage_table(df, ["country", "coicop_2digit"])
    result = _add_coicop_titles_to_result(result, "coicop_2digit", level=2)
    return result


def coverage_coicop_l3_country(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x COICOP level 3."""
    result = coverage_table(df, ["country", "coicop_3digit"])
    result = _add_coicop_titles_to_result(result, "coicop_3digit", level=3)
    return result


def coverage_coicop_l1_country_source(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x source x COICOP level 1."""
    if "source" not in df.columns:
        return coverage_coicop_l1_country(df)
    result = coverage_table(df, ["country", "source", "coicop_1digit"])
    result = _add_coicop_titles_to_result(result, "coicop_1digit", level=1)
    return result


def coverage_coicop_l2_country_source(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x source x COICOP level 2."""
    if "source" not in df.columns:
        return coverage_coicop_l2_country(df)
    result = coverage_table(df, ["country", "source", "coicop_2digit"])
    result = _add_coicop_titles_to_result(result, "coicop_2digit", level=2)
    return result


def coverage_coicop_l3_country_source(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage by country x source x COICOP level 3."""
    if "source" not in df.columns:
        return coverage_coicop_l3_country(df)
    result = coverage_table(df, ["country", "source", "coicop_3digit"])
    result = _add_coicop_titles_to_result(result, "coicop_3digit", level=3)
    return result


# =============================================================================
# TIME COVERAGE TABLES
# =============================================================================


def coverage_time_country_month(df: pd.DataFrame) -> pd.DataFrame:
    """Time coverage by country x month."""
    return coverage_table(df, ["country", "month"])


def coverage_time_source_month(df: pd.DataFrame) -> pd.DataFrame:
    """Time coverage by source x month."""
    if "source" not in df.columns:
        return pd.DataFrame(
            columns=["source", "month", "n_items", "n_obs", "share_items", "share_obs"]
        )
    return coverage_table(df, ["source", "month"])


def coverage_time_country_source_month(df: pd.DataFrame) -> pd.DataFrame:
    """Time coverage by country x source x month."""
    if "source" not in df.columns:
        return coverage_time_country_month(df)
    return coverage_table(df, ["country", "source", "month"])


# =============================================================================
# QUALITY: MISSINGNESS TABLES
# =============================================================================


def quality_missingness_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Compute overall missingness rates for recommended columns."""
    total_rows = len(df)
    records = []
    for col in MISSINGNESS_COLS:
        if col in df.columns:
            missing_count = df[col].isna().sum()
            missing_rate = missing_count / total_rows if total_rows > 0 else 0
        else:
            missing_count = total_rows
            missing_rate = 1.0
        records.append(
            {
                "column": col,
                "missing_count": int(missing_count),
                "missing_rate": missing_rate,
            }
        )
    return pd.DataFrame(records)


def _missingness_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Compute missingness rates by a grouping column."""
    records = []
    for group_val, group_df in df.groupby(group_col):
        total_rows = len(group_df)
        for col in MISSINGNESS_COLS:
            if col in df.columns:
                missing_count = group_df[col].isna().sum()
                missing_rate = missing_count / total_rows if total_rows > 0 else 0
            else:
                missing_count = total_rows
                missing_rate = 1.0
            records.append(
                {
                    group_col: group_val,
                    "column": col,
                    "missing_count": int(missing_count),
                    "missing_rate": missing_rate,
                }
            )
    return pd.DataFrame(records)


def quality_missingness_country(df: pd.DataFrame) -> pd.DataFrame:
    """Compute missingness rates by country."""
    return _missingness_by_group(df, "country")


def quality_missingness_source(df: pd.DataFrame) -> pd.DataFrame:
    """Compute missingness rates by source."""
    if "source" not in df.columns:
        return pd.DataFrame(
            columns=["source", "column", "missing_count", "missing_rate"]
        )
    return _missingness_by_group(df, "source")


# =============================================================================
# QUALITY: DUPLICATES
# =============================================================================


def quality_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute duplicate statistics for (url_hash, date_parsed, source).

    Returns DataFrame with duplicate summary and top duplicate keys.
    """
    if "source" in df.columns:
        dup_cols = ["url_hash", "date_parsed", "source"]
    else:
        dup_cols = ["url_hash", "date_parsed"]

    total_rows = len(df)
    duplicated_mask = df.duplicated(subset=dup_cols, keep=False)
    duplicate_rows = duplicated_mask.sum()
    duplicate_rate = duplicate_rows / total_rows if total_rows > 0 else 0

    # Count occurrences of each key
    key_counts = df.groupby(dup_cols).size().reset_index(name="count")
    # Filter to duplicates only (count > 1)
    dup_keys = key_counts[key_counts["count"] > 1].sort_values("count", ascending=False)

    # Build summary row
    summary = pd.DataFrame(
        [
            {
                "metric": "total_rows",
                "value": total_rows,
            },
            {
                "metric": "duplicate_rows",
                "value": int(duplicate_rows),
            },
            {
                "metric": "duplicate_rate",
                "value": duplicate_rate,
            },
            {
                "metric": "unique_duplicate_keys",
                "value": len(dup_keys),
            },
        ]
    )

    return summary


# =============================================================================
# QUALITY: WAYBACK
# =============================================================================


def quality_wayback_overall(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Wayback Machine statistics overall.

    Returns:
        DataFrame with obs_share_wayback, item_share_wayback, wayback_only_items
    """
    total_obs = len(df)
    total_items = df["url_hash"].nunique()

    wayback_obs = df["is_wayback"].sum()
    obs_share_wayback = wayback_obs / total_obs if total_obs > 0 else 0

    # Items that ever appear as wayback
    items_with_wayback = df[df["is_wayback"]]["url_hash"].nunique()
    item_share_wayback = items_with_wayback / total_items if total_items > 0 else 0

    # Wayback-only items: items that ONLY appear as wayback (never live)
    item_wayback_status = df.groupby("url_hash")["is_wayback"].agg(["any", "all"])
    wayback_only_items = (item_wayback_status["all"]).sum()

    return pd.DataFrame(
        [
            {
                "metric": "obs_share_wayback",
                "value": obs_share_wayback,
            },
            {
                "metric": "item_share_wayback",
                "value": item_share_wayback,
            },
            {
                "metric": "wayback_only_items",
                "value": int(wayback_only_items),
            },
            {
                "metric": "total_obs",
                "value": total_obs,
            },
            {
                "metric": "total_items",
                "value": total_items,
            },
        ]
    )


def quality_wayback_country_source(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Wayback Machine statistics by country x source."""
    if "source" not in df.columns:
        group_cols = ["country"]
    else:
        group_cols = ["country", "source"]

    records = []
    for keys, group_df in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)

        total_obs = len(group_df)
        total_items = group_df["url_hash"].nunique()

        wayback_obs = group_df["is_wayback"].sum()
        obs_share_wayback = wayback_obs / total_obs if total_obs > 0 else 0

        items_with_wayback = group_df[group_df["is_wayback"]]["url_hash"].nunique()
        item_share_wayback = items_with_wayback / total_items if total_items > 0 else 0

        item_wayback_status = group_df.groupby("url_hash")["is_wayback"].agg(
            ["any", "all"]
        )
        wayback_only_items = (item_wayback_status["all"]).sum()

        record = dict(zip(group_cols, keys))
        record.update(
            {
                "obs_share_wayback": obs_share_wayback,
                "item_share_wayback": item_share_wayback,
                "wayback_only_items": int(wayback_only_items),
                "total_obs": total_obs,
                "total_items": total_items,
            }
        )
        records.append(record)

    return pd.DataFrame(records)


# =============================================================================
# DISTRIBUTION: unit_value STATS
# =============================================================================


def unit_value_stats(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    """
    Compute unit_value distribution statistics by group.

    Args:
        df: Validated DataFrame
        group_cols: Columns to group by

    Returns:
        DataFrame with n_items, n_obs, min, max, mean, std, and quantiles
    """

    def compute_stats(group_df: pd.DataFrame) -> pd.Series:
        values = group_df["unit_value"].dropna()
        return pd.Series(
            {
                "n_items": group_df["url_hash"].nunique(),
                "n_obs": len(group_df),
                "min": values.min() if len(values) > 0 else np.nan,
                "p1": values.quantile(0.01) if len(values) > 0 else np.nan,
                "p5": values.quantile(0.05) if len(values) > 0 else np.nan,
                "p25": values.quantile(0.25) if len(values) > 0 else np.nan,
                "median": values.median() if len(values) > 0 else np.nan,
                "p75": values.quantile(0.75) if len(values) > 0 else np.nan,
                "p95": values.quantile(0.95) if len(values) > 0 else np.nan,
                "p99": values.quantile(0.99) if len(values) > 0 else np.nan,
                "max": values.max() if len(values) > 0 else np.nan,
                "mean": values.mean() if len(values) > 0 else np.nan,
                "std": values.std() if len(values) > 0 else np.nan,
            }
        )

    result = (
        df.groupby(group_cols).apply(compute_stats, include_groups=False).reset_index()
    )
    return result


def dist_unit_value_country(df: pd.DataFrame) -> pd.DataFrame:
    """unit_value distribution by country."""
    return unit_value_stats(df, ["country"])


def dist_unit_value_country_source(df: pd.DataFrame) -> pd.DataFrame:
    """unit_value distribution by country x source."""
    if "source" not in df.columns:
        return dist_unit_value_country(df)
    return unit_value_stats(df, ["country", "source"])


def dist_unit_value_country_coicop_l3(df: pd.DataFrame) -> pd.DataFrame:
    """unit_value distribution by country x COICOP level 3."""
    return unit_value_stats(df, ["country", "coicop_3digit"])


# =============================================================================
# OUTLIERS
# =============================================================================


def outliers_unit_value_country_coicop_l3(
    df: pd.DataFrame,
    low_q: float = 0.01,
    high_q: float = 0.99,
) -> pd.DataFrame:
    """
    Flag outliers based on quantile thresholds within (country, coicop_3digit) groups.

    Args:
        df: Validated DataFrame
        low_q: Lower quantile threshold (default 0.01)
        high_q: Upper quantile threshold (default 0.99)

    Returns:
        DataFrame with outlier flags and thresholds for each row
    """
    # Compute thresholds by group
    thresholds = (
        df.groupby(["country", "coicop_3digit"])["unit_value"]
        .agg(
            low_threshold=lambda x: x.quantile(low_q),
            high_threshold=lambda x: x.quantile(high_q),
        )
        .reset_index()
    )

    # Merge thresholds back to original data
    result = df.merge(thresholds, on=["country", "coicop_3digit"], how="left")

    # Flag outliers
    result["is_outlier"] = (result["unit_value"] < result["low_threshold"]) | (
        result["unit_value"] > result["high_threshold"]
    )

    # Select output columns
    output_cols = ["url_hash", "country", "coicop_3digit", "coicop_code", "date_parsed"]
    if "source" in df.columns:
        output_cols.insert(2, "source")
    output_cols.extend(["unit_value", "low_threshold", "high_threshold", "is_outlier"])

    # Filter to outliers only for the output
    outliers = result[result["is_outlier"]][output_cols].copy()
    outliers = outliers.sort_values(
        ["country", "coicop_3digit", "unit_value"], ascending=[True, True, False]
    )

    return outliers.reset_index(drop=True)


def _outliers_uv_coicop_summary(df: pd.DataFrame, coicop_col: str) -> pd.DataFrame:
    """
    Compute outliers summary by COICOP level showing share of items and obs > p75.

    Args:
        df: Validated DataFrame
        coicop_col: COICOP column name (e.g., 'coicop_1digit', 'coicop_2digit')

    Returns:
        DataFrame with coicop_Ndigit, n_items, n_obs, mean_uv, std_uv, share_items_uv_gt_p75, share_obs_uv_gt_p75, share_items_uv_gt_p9, share_obs_uv_gt_p9
    """
    records = []

    for coicop_val, group_df in df.groupby(coicop_col):
        n_items = group_df["url_hash"].nunique()
        n_obs = len(group_df)
        mean_uv = group_df["unit_value"].mean()
        std_uv = group_df["unit_value"].std()

        # Calculate p75 for this COICOP group
        p75 = group_df["unit_value"].quantile(0.75)

        # Items with any observation > p75
        items_gt_p75 = group_df[group_df["unit_value"] > p75]["url_hash"].nunique()
        share_items_uv_gt_p75 = items_gt_p75 / n_items if n_items > 0 else 0

        # Observations > p75
        obs_gt_p75 = (group_df["unit_value"] > p75).sum()
        share_obs_uv_gt_p75 = obs_gt_p75 / n_obs if n_obs > 0 else 0

        # Calculate p90 for this COICOP group
        p90 = group_df["unit_value"].quantile(0.90)

        # Items with any observation > p90
        items_gt_p90 = group_df[group_df["unit_value"] > p90]["url_hash"].nunique()
        share_items_uv_gt_p9 = items_gt_p90 / n_items if n_items > 0 else 0

        # Observations > p90
        obs_gt_p90 = (group_df["unit_value"] > p90).sum()
        share_obs_uv_gt_p9 = obs_gt_p90 / n_obs if n_obs > 0 else 0

        records.append(
            {
                coicop_col: coicop_val,
                "n_items": n_items,
                "n_obs": n_obs,
                "mean_uv": mean_uv,
                "std_uv": std_uv,
                "share_items_uv_gt_p75": share_items_uv_gt_p75,
                "share_obs_uv_gt_p75": share_obs_uv_gt_p75,
                "share_items_uv_gt_p9": share_items_uv_gt_p9,
                "share_obs_uv_gt_p9": share_obs_uv_gt_p9,
            }
        )

    result = pd.DataFrame(records)
    result = result.sort_values(coicop_col).reset_index(drop=True)
    return result


def outliers_uv_coicop_l1_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by COICOP level 1 (overall)."""
    result = _outliers_uv_coicop_summary(df, "coicop_1digit")
    result = _add_coicop_titles_to_result(result, "coicop_1digit", level=1)
    return result


def outliers_uv_coicop_l2_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by COICOP level 2 (overall)."""
    result = _outliers_uv_coicop_summary(df, "coicop_2digit")
    result = _add_coicop_titles_to_result(result, "coicop_2digit", level=2)
    return result


def outliers_uv_coicop_l3_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by COICOP level 3 (overall)."""
    result = _outliers_uv_coicop_summary(df, "coicop_3digit")
    result = _add_coicop_titles_to_result(result, "coicop_3digit", level=3)
    return result


def outliers_uv_coicop_l4_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by COICOP level 4 (overall)."""
    result = _outliers_uv_coicop_summary(df, "coicop_code")
    result = _add_coicop_titles_to_result(result, "coicop_code", level=4)
    return result


def _outliers_uv_coicop_country_summary(
    df: pd.DataFrame, coicop_col: str
) -> pd.DataFrame:
    """
    Compute outliers summary by country x COICOP level showing share of items and obs > p75.

    Args:
        df: Validated DataFrame
        coicop_col: COICOP column name (e.g., 'coicop_1digit', 'coicop_2digit')

    Returns:
        DataFrame with country, coicop_Ndigit, n_items, n_obs, mean_uv, std_uv, share_items_uv_gt_p75, share_obs_uv_gt_p75, share_items_uv_gt_p9, share_obs_uv_gt_p9
    """
    records = []

    for (country, coicop_val), group_df in df.groupby(["country", coicop_col]):
        n_items = group_df["url_hash"].nunique()
        n_obs = len(group_df)
        mean_uv = group_df["unit_value"].mean()
        std_uv = group_df["unit_value"].std()

        # Calculate p75 for this country x COICOP group
        p75 = group_df["unit_value"].quantile(0.75)

        # Items with any observation > p75
        items_gt_p75 = group_df[group_df["unit_value"] > p75]["url_hash"].nunique()
        share_items_uv_gt_p75 = items_gt_p75 / n_items if n_items > 0 else 0

        # Observations > p75
        obs_gt_p75 = (group_df["unit_value"] > p75).sum()
        share_obs_uv_gt_p75 = obs_gt_p75 / n_obs if n_obs > 0 else 0

        # Calculate p90 for this country x COICOP group
        p90 = group_df["unit_value"].quantile(0.90)

        # Items with any observation > p90
        items_gt_p90 = group_df[group_df["unit_value"] > p90]["url_hash"].nunique()
        share_items_uv_gt_p9 = items_gt_p90 / n_items if n_items > 0 else 0

        # Observations > p90
        obs_gt_p90 = (group_df["unit_value"] > p90).sum()
        share_obs_uv_gt_p9 = obs_gt_p90 / n_obs if n_obs > 0 else 0

        records.append(
            {
                "country": country,
                coicop_col: coicop_val,
                "n_items": n_items,
                "n_obs": n_obs,
                "mean_uv": mean_uv,
                "std_uv": std_uv,
                "share_items_uv_gt_p75": share_items_uv_gt_p75,
                "share_obs_uv_gt_p75": share_obs_uv_gt_p75,
                "share_items_uv_gt_p9": share_items_uv_gt_p9,
                "share_obs_uv_gt_p9": share_obs_uv_gt_p9,
            }
        )

    result = pd.DataFrame(records)
    result = result.sort_values(["country", coicop_col]).reset_index(drop=True)
    return result


def outliers_uv_coicop_l1_country(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by country x COICOP level 1."""
    result = _outliers_uv_coicop_country_summary(df, "coicop_1digit")
    result = _add_coicop_titles_to_result(result, "coicop_1digit", level=1)
    return result


def outliers_uv_coicop_l2_country(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by country x COICOP level 2."""
    result = _outliers_uv_coicop_country_summary(df, "coicop_2digit")
    result = _add_coicop_titles_to_result(result, "coicop_2digit", level=2)
    return result


def outliers_uv_coicop_l3_country(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by country x COICOP level 3."""
    result = _outliers_uv_coicop_country_summary(df, "coicop_3digit")
    result = _add_coicop_titles_to_result(result, "coicop_3digit", level=3)
    return result


def outliers_uv_coicop_l4_country(df: pd.DataFrame) -> pd.DataFrame:
    """Outliers summary by country x COICOP level 4."""
    result = _outliers_uv_coicop_country_summary(df, "coicop_code")
    result = _add_coicop_titles_to_result(result, "coicop_code", level=4)
    return result
