"""Data cleaning and filtering operations."""

import pandas as pd
import numpy as np
from typing import List, Optional


def filter_usable(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to usable observations based on usability_status.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with 'usability_status' column

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame containing only rows where usability_status
        starts with "resolved"
    """
    return df[df["usability_status"].str.startswith("resolved", na=False)].copy()


def filter_by_tier(
    df: pd.DataFrame, tiers: Optional[List[float]] = None
) -> pd.DataFrame:
    """
    Filter observations by extraction tier.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with 'extraction_tier' column
    tiers : list of float, optional
        List of tiers to keep (e.g., [1.0, 2.0])
        If None, returns all tiers

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame
    """
    if tiers is None:
        return df.copy()

    return df[df["extraction_tier"].isin(tiers)].copy()


def compute_log_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add log-transformed unit_value column.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with 'unit_value' column

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'log_unit_value' column

    Notes
    -----
    Filters out zero and negative prices before computing log.
    """
    df = df.copy()

    # Filter out invalid prices
    valid_prices = df["unit_value"] > 0

    # Compute log prices
    df.loc[valid_prices, "log_unit_value"] = np.log(df.loc[valid_prices, "unit_value"])

    return df
