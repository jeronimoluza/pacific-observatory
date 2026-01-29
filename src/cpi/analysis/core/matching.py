"""Time-series matching and price change computation."""

import pandas as pd


def create_matched_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create matched pairs of consecutive month observations for each product.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with columns:
        - url_hash: Product identifier
        - year_month: Period identifier (YYYY-MM)
        - log_unit_value: Log price
        - country, coicop_1, coicop_2, coicop_3, coicop_4, extraction_tier

    Returns
    -------
    pd.DataFrame
        DataFrame with matched pairs containing:
        - url_hash: Product identifier
        - year_month_t: Current period
        - year_month_t1: Previous period
        - log_price_t: Current log price
        - log_price_t1: Previous log price
        - country, coicop_1, coicop_2, coicop_3, coicop_4, extraction_tier

    Notes
    -----
    Only creates pairs for consecutive months (no gaps).
    """
    # Filter out rows with missing log prices
    df = df[df["log_unit_value"].notna()].copy()

    # Sort by product and time
    df = df.sort_values(["url_hash", "year_month"]).copy()

    # Convert year_month to period for proper date arithmetic
    df["period"] = pd.to_datetime(df["year_month"]).dt.to_period("M")

    # Create lagged values within each product
    df["period_lag"] = df.groupby("url_hash")["period"].shift(1)
    df["log_price_lag"] = df.groupby("url_hash")["log_unit_value"].shift(1)
    df["year_month_lag"] = df.groupby("url_hash")["year_month"].shift(1)

    # Keep only consecutive months (difference of 1 period)
    df["is_consecutive"] = (df["period"] - df["period_lag"]) == 1

    # Filter to valid matches (consecutive months with non-null lagged values)
    matched = df[df["is_consecutive"] & df["log_price_lag"].notna()].copy()

    # Rename columns for clarity
    matched = matched.rename(
        columns={
            "year_month": "year_month_t",
            "log_unit_value": "log_price_t",
            "year_month_lag": "year_month_t1",
            "log_price_lag": "log_price_t1",
        }
    )

    # Select relevant columns
    keep_cols = [
        "url_hash",
        "year_month_t",
        "year_month_t1",
        "log_price_t",
        "log_price_t1",
        "country",
        "coicop_1",
        "coicop_2",
        "coicop_3",
        "coicop_4",
        "extraction_tier",
    ]

    # Keep only columns that exist
    keep_cols = [col for col in keep_cols if col in matched.columns]

    return matched[keep_cols].reset_index(drop=True)


def compute_price_changes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute log price changes from matched pairs.

    Parameters
    ----------
    df : pd.DataFrame
        Matched pairs DataFrame with log_price_t and log_price_t1 columns

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'delta_p' column containing log price changes
        delta_p = log(p_t) - log(p_{t-1})
    """
    df = df.copy()
    df["delta_p"] = df["log_price_t"] - df["log_price_t1"]
    return df
