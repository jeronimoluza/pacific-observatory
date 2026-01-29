"""Inflation breadth and diffusion indices."""

import pandas as pd
import numpy as np
from typing import List


def compute_diffusion(df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Compute diffusion indices measuring breadth of price changes.

    Parameters
    ----------
    df : pd.DataFrame
        Matched pairs DataFrame with 'delta_p' column (log price changes)
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'year_month_t'])

    Returns
    -------
    pd.DataFrame
        Diffusion statistics with columns:
        - groupby_cols: Grouping columns
        - share_increase: Share of products with price increases (delta_p > 0)
        - share_decrease: Share of products with price decreases (delta_p < 0)
        - share_large_10: Share with >10% price increase (delta_p > log(1.10))
        - share_large_20: Share with >20% price increase (delta_p > log(1.20))
        - n_products: Number of products

    Notes
    -----
    All shares are proportions (0 to 1).
    Large increases use log thresholds: log(1.10) ≈ 0.0953, log(1.20) ≈ 0.1823
    """

    def compute_shares(group):
        """Compute diffusion shares for a group."""
        delta_p = group["delta_p"]
        n = len(delta_p)

        if n == 0:
            return pd.Series(
                {
                    "share_increase": np.nan,
                    "share_decrease": np.nan,
                    "share_large_10": np.nan,
                    "share_large_20": np.nan,
                    "n_products": 0,
                }
            )

        return pd.Series(
            {
                "share_increase": (delta_p > 0).mean(),
                "share_decrease": (delta_p < 0).mean(),
                "share_large_10": (delta_p > np.log(1.10)).mean(),
                "share_large_20": (delta_p > np.log(1.20)).mean(),
                "n_products": n,
            }
        )

    result = df.groupby(groupby_cols, as_index=False).apply(
        compute_shares, include_groups=False
    )

    return result
