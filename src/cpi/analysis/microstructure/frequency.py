"""Price change frequency metrics."""

import pandas as pd
import numpy as np
from typing import List


def compute_change_frequency(df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Compute the frequency of price changes from matched pairs.

    Parameters
    ----------
    df : pd.DataFrame
        Matched pairs DataFrame with 'delta_p' column (log price changes)
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'coicop_1', 'year_month_t'])

    Returns
    -------
    pd.DataFrame
        Change frequency statistics with columns:
        - groupby_cols: Grouping columns
        - share_changed: Share of products with any price change
        - share_unchanged: Share of products with no price change
        - share_increased: Share of products with price increase
        - share_decreased: Share of products with price decrease
        - n_products: Number of matched products
    """

    def compute_shares(group):
        delta_p = group["delta_p"]
        n = len(delta_p)

        if n == 0:
            return pd.Series(
                {
                    "share_changed": np.nan,
                    "share_unchanged": np.nan,
                    "share_increased": np.nan,
                    "share_decreased": np.nan,
                    "n_products": 0,
                }
            )

        changed = delta_p.abs() > 1e-9
        return pd.Series(
            {
                "share_changed": changed.mean(),
                "share_unchanged": (~changed).mean(),
                "share_increased": (delta_p > 1e-9).mean(),
                "share_decreased": (delta_p < -1e-9).mean(),
                "n_products": n,
            }
        )

    result = df.groupby(groupby_cols, as_index=False).apply(
        compute_shares, include_groups=False
    )

    return result
