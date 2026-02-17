"""PPP price level comparisons across countries."""

import pandas as pd
import numpy as np
from typing import List


def compute_price_levels_usd(df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Compute price levels in USD for cross-country comparison.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with 'unit_value_usd' column (output of convert_to_usd)
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'coicop_1', 'year_month'])

    Returns
    -------
    pd.DataFrame
        Price level statistics with columns:
        - groupby_cols: Grouping columns
        - price_level_usd_mean: Mean USD price
        - price_level_usd_median: Median USD price
        - n_products: Total products in group
        - n_products_with_fx: Products with valid FX conversion
    """
    # Only use rows with valid USD prices for aggregation
    valid = df[df["unit_value_usd"].notna()].copy()

    def agg_group(group):
        usd = group["unit_value_usd"]
        n_total = len(group)
        n_valid = usd.notna().sum()

        if n_valid == 0:
            return pd.Series(
                {
                    "price_level_usd_mean": np.nan,
                    "price_level_usd_median": np.nan,
                    "n_products": n_total,
                    "n_products_with_fx": 0,
                }
            )

        return pd.Series(
            {
                "price_level_usd_mean": usd.mean(),
                "price_level_usd_median": usd.median(),
                "n_products": n_total,
                "n_products_with_fx": n_valid,
            }
        )

    result = valid.groupby(groupby_cols, as_index=False).apply(
        agg_group, include_groups=False
    )

    return result


def compute_ppp_ratios(
    price_levels_df: pd.DataFrame,
    groupby_cols: List[str],
    reference: str = "cross_country_median",
) -> pd.DataFrame:
    """
    Compute PPP ratios comparing each country's price level to a reference.

    Parameters
    ----------
    price_levels_df : pd.DataFrame
        Output of compute_price_levels_usd() with 'price_level_usd_median' column
    groupby_cols : list of str
        Columns to group by. Must include 'country' and typically a COICOP level
        and time period (e.g., ['country', 'coicop_1', 'year_month'])
    reference : str
        Reference for PPP ratio computation:
        - "cross_country_median": Median of all countries' median prices (default)
        - "cross_country_mean": Mean of all countries' median prices
        - A country slug (e.g., "australia"): Use that country's price as reference

    Returns
    -------
    pd.DataFrame
        PPP ratios with columns:
        - groupby_cols: Grouping columns
        - price_level_usd_median: Country's median USD price
        - reference_price_usd: Reference price used
        - ppp_ratio: Ratio of country price to reference (>1 = more expensive)
        - n_products: Number of products
    """
    df = price_levels_df.copy()

    # Identify the non-country grouping columns (e.g., coicop + time)
    non_country_cols = [c for c in groupby_cols if c != "country"]

    if reference == "cross_country_mean":
        ref = (
            df.groupby(non_country_cols)["price_level_usd_median"]
            .mean()
            .reset_index()
            .rename(columns={"price_level_usd_median": "reference_price_usd"})
        )
    elif reference == "cross_country_median":
        ref = (
            df.groupby(non_country_cols)["price_level_usd_median"]
            .median()
            .reset_index()
            .rename(columns={"price_level_usd_median": "reference_price_usd"})
        )
    else:
        # Use a specific country as reference
        ref = df[df["country"] == reference][
            non_country_cols + ["price_level_usd_median"]
        ].rename(columns={"price_level_usd_median": "reference_price_usd"})

    # Merge reference prices
    df = df.merge(ref, on=non_country_cols, how="left")

    # Compute PPP ratio
    df["ppp_ratio"] = df["price_level_usd_median"] / df["reference_price_usd"]

    keep_cols = groupby_cols + [
        "price_level_usd_median",
        "reference_price_usd",
        "ppp_ratio",
        "n_products",
    ]
    keep_cols = [c for c in keep_cols if c in df.columns]

    return df[keep_cols].reset_index(drop=True)
