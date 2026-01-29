"""Time-series matching and price change computation."""

import pandas as pd


def create_matched_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create matched pairs of observations for each product across available months.

    Designed for snapshot panel data (e.g., web-scraped prices with Wayback Machine
    historical data) where products may not appear in consecutive months due to
    scraping gaps and irregular data collection.

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
        - months_gap: Number of months between observations
        - log_price_t: Current log price
        - log_price_t1: Previous log price
        - country, coicop_1, coicop_2, coicop_3, coicop_4, extraction_tier

    Notes
    -----
    Matches any available pairs for the same product, not just consecutive months.
    The `months_gap` column indicates the time gap between observations.
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

    # Compute months gap between observations
    df["months_gap"] = (df["period"] - df["period_lag"]).apply(
        lambda x: x.n if pd.notna(x) else None
    )
    # Filter to valid matches (any pair with non-null lagged values)
    matched = df[(df["log_price_lag"].notna()) & (df["months_gap"] == 1)].copy()

    # matched = df[df["log_price_lag"].notna()].copy()

    # Rename columns for clarity
    matched = matched.rename(
        columns={
            "year_month": "year_month_t",
            "log_unit_value": "log_price_t",
            "year_month_lag": "year_month_t1",
            "log_price_lag": "log_price_t1",
        }
    )

    # Keep months_gap column for analysis

    # Select relevant columns
    keep_cols = [
        "url_hash",
        "year_month_t",
        "year_month_t1",
        "months_gap",
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
