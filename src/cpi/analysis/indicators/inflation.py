"""Core inflation calculations and price level tracking."""

import pandas as pd
from typing import List
from scipy import stats


def aggregate_inflation(df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Compute matched-model inflation by aggregating price changes.

    Parameters
    ----------
    df : pd.DataFrame
        Matched pairs DataFrame with 'delta_p' column (log price changes)
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'year_month_t'])

    Returns
    -------
    pd.DataFrame
        Aggregated inflation statistics with columns:
        - groupby_cols: Grouping columns
        - inflation_mean: Mean log price change
        - inflation_median: Median log price change
        - inflation_trimmed_mean: 5% trimmed mean
        - n_products: Number of matched products

    Notes
    -----
    Trimmed mean removes top and bottom 5% of observations.
    """

    def trimmed_mean_5pct(x):
        """Compute 5% trimmed mean."""
        if len(x) < 10:  # Need at least 10 obs for meaningful trimming
            return x.mean()
        return stats.trim_mean(x, 0.05)

    agg_dict = {
        "delta_p": [
            ("inflation_mean", "mean"),
            ("inflation_median", "median"),
            ("inflation_trimmed_mean", trimmed_mean_5pct),
            ("n_products", "count"),
        ]
    }

    result = df.groupby(groupby_cols).agg(agg_dict)
    result.columns = [col[1] if col[1] else col[0] for col in result.columns]
    result = result.reset_index()

    return result


def compute_price_levels(df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Track log price levels over time.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'log_unit_value' column
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'year_month'])

    Returns
    -------
    pd.DataFrame
        Price level statistics with columns:
        - groupby_cols: Grouping columns
        - price_level_mean: Mean log price
        - price_level_median: Median log price
        - price_level_q1: 25th percentile
        - price_level_q3: 75th percentile
        - price_level_iqr: Interquartile range
        - n_observations: Number of observations

    Notes
    -----
    Uses log(unit_value) for price levels.
    """
    agg_dict = {
        "log_unit_value": [
            ("price_level_mean", "mean"),
            ("price_level_median", "median"),
            ("price_level_q1", lambda x: x.quantile(0.25)),
            ("price_level_q3", lambda x: x.quantile(0.75)),
            ("n_observations", "count"),
        ]
    }

    result = df.groupby(groupby_cols).agg(agg_dict)
    result.columns = [col[1] if col[1] else col[0] for col in result.columns]
    result = result.reset_index()

    # Compute IQR
    result["price_level_iqr"] = result["price_level_q3"] - result["price_level_q1"]

    return result
