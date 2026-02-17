"""Price spell computation and stickiness classification."""

import pandas as pd
import numpy as np
from typing import List


def compute_price_spells(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute price spells — consecutive periods where a product's price is unchanged.

    Uses the raw preprocessed DataFrame (not matched pairs) since we need
    consecutive observations per product.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed DataFrame with columns:
        - url_hash: Product identifier
        - year_month: Period identifier (YYYY-MM)
        - unit_value: Price
        - country, coicop_1, coicop_2, coicop_3, coicop_4

    Returns
    -------
    pd.DataFrame
        One row per spell with columns:
        - url_hash: Product identifier
        - spell_start: First year_month of the spell
        - spell_end: Last year_month of the spell
        - spell_length: Duration in months
        - price_at_spell: Price during the spell
        - is_censored: True if spell is ongoing at end of observation window
        - country, coicop_1, coicop_2, coicop_3, coicop_4
    """
    # Work with valid prices only
    df = df[df["unit_value"].notna() & (df["unit_value"] > 0)].copy()
    df = df.sort_values(["url_hash", "year_month"])

    # Convert year_month to period for gap detection
    df["period"] = pd.to_datetime(df["year_month"]).dt.to_period("M")

    # Detect spell boundaries within each product
    df["prev_price"] = df.groupby("url_hash")["unit_value"].shift(1)
    df["prev_period"] = df.groupby("url_hash")["period"].shift(1)

    # A spell breaks if: price changes OR gap > 1 month
    df["price_changed"] = ~np.isclose(
        df["unit_value"], df["prev_price"], rtol=1e-9, equal_nan=True
    )
    df["gap"] = (df["period"] - df["prev_period"]).apply(
        lambda x: x.n if pd.notna(x) else None
    )
    df["new_spell"] = df["price_changed"] | (df["gap"] != 1) | df["prev_price"].isna()

    # Assign spell IDs
    df["spell_id"] = df.groupby("url_hash")["new_spell"].cumsum()

    # Determine the last year_month per product (for censoring)
    # max_period_per_product = df.groupby("url_hash")["period"].transform("max")

    # Aggregate spells
    meta_cols = ["country", "coicop_1", "coicop_2", "coicop_3", "coicop_4"]
    meta_cols = [c for c in meta_cols if c in df.columns]

    group_cols = ["url_hash", "spell_id"]
    spells = (
        df.groupby(group_cols)
        .agg(
            spell_start=("year_month", "first"),
            spell_end=("year_month", "last"),
            spell_length=("year_month", "count"),
            price_at_spell=("unit_value", "first"),
            last_period=("period", "max"),
            product_max_period=("period", "last"),
            **{col: (col, "first") for col in meta_cols},
        )
        .reset_index()
    )

    # Determine censoring: spell is censored if it ends at the product's last observation
    product_max = df.groupby("url_hash")["period"].max().reset_index()
    product_max.columns = ["url_hash", "product_max"]
    spells = spells.merge(product_max, on="url_hash", how="left")
    spells["is_censored"] = spells["last_period"] == spells["product_max"]

    # Clean up columns
    keep_cols = [
        "url_hash",
        "spell_start",
        "spell_end",
        "spell_length",
        "price_at_spell",
        "is_censored",
    ] + meta_cols
    return spells[keep_cols].reset_index(drop=True)


def aggregate_spells(spells_df: pd.DataFrame, groupby_cols: List[str]) -> pd.DataFrame:
    """
    Aggregate spell statistics by group.

    Parameters
    ----------
    spells_df : pd.DataFrame
        Output of compute_price_spells()
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'coicop_1'])

    Returns
    -------
    pd.DataFrame
        Aggregated spell statistics with columns:
        - groupby_cols: Grouping columns
        - mean_spell_length: Mean spell duration (months)
        - median_spell_length: Median spell duration
        - p25_spell_length: 25th percentile
        - p75_spell_length: 75th percentile
        - share_sticky: Share of spells >= 3 months
        - share_flexible: Share of spells == 1 month
        - n_spells: Number of spells
        - n_products: Number of unique products
    """

    def agg_group(group):
        lengths = group["spell_length"]
        n = len(lengths)

        if n == 0:
            return pd.Series(
                {
                    "mean_spell_length": np.nan,
                    "median_spell_length": np.nan,
                    "p25_spell_length": np.nan,
                    "p75_spell_length": np.nan,
                    "share_sticky": np.nan,
                    "share_flexible": np.nan,
                    "n_spells": 0,
                    "n_products": 0,
                }
            )

        return pd.Series(
            {
                "mean_spell_length": lengths.mean(),
                "median_spell_length": lengths.median(),
                "p25_spell_length": lengths.quantile(0.25),
                "p75_spell_length": lengths.quantile(0.75),
                "share_sticky": (lengths >= 3).mean(),
                "share_flexible": (lengths == 1).mean(),
                "n_spells": n,
                "n_products": group["url_hash"].nunique(),
            }
        )

    result = spells_df.groupby(groupby_cols, as_index=False).apply(
        agg_group, include_groups=False
    )

    return result


def classify_sticky_flexible(
    spells_df: pd.DataFrame,
    groupby_cols: List[str],
    sticky_threshold: int = 3,
) -> pd.DataFrame:
    """
    Classify products as sticky or flexible based on their mean spell length.

    Parameters
    ----------
    spells_df : pd.DataFrame
        Output of compute_price_spells()
    groupby_cols : list of str
        Columns to group by (e.g., ['country', 'coicop_1'])
    sticky_threshold : int
        Minimum mean spell length (months) to classify as sticky (default: 3)

    Returns
    -------
    pd.DataFrame
        Classification with columns:
        - groupby_cols: Grouping columns
        - share_sticky_products: Share of products classified as sticky
        - share_flexible_products: Share of products classified as flexible
        - n_products: Number of unique products
    """
    # Compute mean spell length per product within each group
    product_cols = groupby_cols + ["url_hash"]
    product_means = (
        spells_df.groupby(product_cols)["spell_length"]
        .mean()
        .reset_index()
        .rename(columns={"spell_length": "mean_spell_length"})
    )

    # Classify each product
    product_means["is_sticky"] = product_means["mean_spell_length"] >= sticky_threshold

    def classify_group(group):
        n = len(group)
        if n == 0:
            return pd.Series(
                {
                    "share_sticky_products": np.nan,
                    "share_flexible_products": np.nan,
                    "n_products": 0,
                }
            )

        return pd.Series(
            {
                "share_sticky_products": group["is_sticky"].mean(),
                "share_flexible_products": (~group["is_sticky"]).mean(),
                "n_products": n,
            }
        )

    result = product_means.groupby(groupby_cols, as_index=False).apply(
        classify_group, include_groups=False
    )

    return result
