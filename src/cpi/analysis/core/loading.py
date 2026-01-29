"""Data loading and I/O operations."""

import pandas as pd
from pathlib import Path
from typing import Union


def load_prices(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Load price data from CSV file.

    Parameters
    ----------
    filepath : str or Path
        Path to the CSV file containing price data

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - url_hash: Product identifier
        - unit_value: Standardized price
        - usability_status: Quality classification
        - extraction_tier: Quality tier (1.0, 2.0, 3.0)
        - coicop_code: COICOP classification
        - country: Country code
        - date: Observation timestamp (datetime)
        - year_month: YYYY-MM format string
        - price, currency, amount, units, standard_unit
    """
    # Define dtypes for efficient loading
    dtypes = {
        "url_hash": str,
        "unit_value": float,
        "usability_status": str,
        "extraction_tier": float,
        "coicop_code": str,
        "country": str,
        "price": float,
        "currency": str,
    }

    # Load CSV
    df = pd.read_csv(filepath, dtype=dtypes, parse_dates=["date"])

    # Add year_month column
    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    return df


def save_results(df: pd.DataFrame, filepath: Union[str, Path]) -> None:
    """
    Save results DataFrame to CSV.

    Parameters
    ----------
    df : pd.DataFrame
        Results DataFrame to save
    filepath : str or Path
        Output file path
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)
