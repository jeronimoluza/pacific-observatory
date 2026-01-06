"""
Data Loader for CPI Construction.

Loads and validates price data with COICOP classifications.
Filters to Division 01 (Food and non-alcoholic beverages).
Maps 4-digit COICOP codes to 3-digit parent categories.
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.utils import (
        extract_month,
        coicop_4digit_to_3digit,
        is_division_01,
        validate_coicop_code,
    )
else:
    from .utils import (
        extract_month,
        coicop_4digit_to_3digit,
        is_division_01,
        validate_coicop_code,
    )


# Expected columns in the price data
REQUIRED_COLUMNS = [
    "url_hash",
    "unit_value",
    "date",
    "coicop_code",
    "country",
]

OPTIONAL_COLUMNS = [
    "product_name",
    "product_w_cat",
    "currency",
    "amount",
    "units",
    "unit_value",
    "coicop_title",
    "source",
    "product_url",
    "product_id",
    "wayback",
]


def load_price_data(
    filepath: str | Path,
    country: Optional[str] = None,
    division_01_only: bool = True,
) -> pd.DataFrame:
    """
    Load price data from CSV file.

    Args:
        filepath: Path to the price data CSV
        country: Optional country filter (e.g., 'fiji', 'australia')
        division_01_only: If True, filter to COICOP Division 01 only

    Returns:
        DataFrame with validated price data

    Raises:
        FileNotFoundError: If filepath doesn't exist
        ValueError: If required columns are missing
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Price data file not found: {filepath}")

    print(f"Loading price data from {filepath}...")
    df = pd.read_csv(filepath, encoding="utf-8")

    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    print(f"  Loaded {len(df):,} rows")

    # Filter by country if specified
    if country:
        country_lower = country.lower()
        df = df[df["country"].str.lower() == country_lower]
        print(f"  Filtered to country '{country}': {len(df):,} rows")

    # Filter to Division 01 if specified
    if division_01_only:
        df = df[df["coicop_code"].apply(is_division_01)]
        print(f"  Filtered to Division 01: {len(df):,} rows")

    return df


def validate_price_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Validate and clean price data.

    Performs:
    - Validate unit_value is numeric and positive
    - Validate COICOP codes
    - Parse dates
    - Remove invalid rows

    Args:
        df: Raw price DataFrame

    Returns:
        Tuple of (cleaned DataFrame, validation stats dict)
    """
    stats = {
        "total_rows": len(df),
        "invalid_unit_values": 0,
        "invalid_coicop": 0,
        "invalid_dates": 0,
        "valid_rows": 0,
    }

    df = df.copy()

    # Validate unit_value (should already be numeric)
    df["unit_value"] = pd.to_numeric(df["unit_value"], errors="coerce")
    invalid_unit_values = df["unit_value"].isna() | (df["unit_value"] <= 0)
    stats["invalid_unit_values"] = invalid_unit_values.sum()

    # Validate COICOP codes
    invalid_coicop = ~df["coicop_code"].apply(validate_coicop_code)
    stats["invalid_coicop"] = invalid_coicop.sum()

    # Parse dates
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    invalid_dates = df["date_parsed"].isna()
    stats["invalid_dates"] = invalid_dates.sum()

    # Remove invalid rows
    valid_mask = ~invalid_unit_values & ~invalid_coicop & ~invalid_dates
    df_valid = df[valid_mask].copy()
    stats["valid_rows"] = len(df_valid)

    print(f"  Validation: {stats['valid_rows']:,} valid rows")
    if stats["invalid_unit_values"] > 0:
        print(
            f"    - Removed {stats['invalid_unit_values']:,} rows with invalid unit_values"
        )
    if stats["invalid_coicop"] > 0:
        print(
            f"    - Removed {stats['invalid_coicop']:,} rows with invalid COICOP codes"
        )
    if stats["invalid_dates"] > 0:
        print(f"    - Removed {stats['invalid_dates']:,} rows with invalid dates")

    return df_valid, stats


def prepare_for_cpi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare validated data for CPI calculation.

    Adds:
    - month: Year-month string (YYYY-MM)
    - coicop_3digit: 3-digit COICOP parent category

    Note: unit_value column is already present and validated.

    Args:
        df: Validated price DataFrame

    Returns:
        DataFrame ready for CPI calculation
    """
    df = df.copy()

    # Extract month
    df["month"] = extract_month(df["date_parsed"])

    # Map to 3-digit COICOP
    df["coicop_3digit"] = df["coicop_code"].apply(coicop_4digit_to_3digit)

    print("  Prepared data:")
    print(
        f"    - Months: {df['month'].nunique()} ({df['month'].min()} to {df['month'].max()})"
    )
    print(f"    - Articles (url_hash): {df['url_hash'].nunique():,}")
    print(f"    - 3-digit COICOP categories: {df['coicop_3digit'].nunique()}")

    return df


def load_and_prepare(
    filepath: str | Path,
    country: Optional[str] = None,
    division_01_only: bool = True,
) -> Tuple[pd.DataFrame, dict]:
    """
    Load, validate, and prepare price data for CPI calculation.

    This is the main entry point for the data loading module.

    Args:
        filepath: Path to the price data CSV
        country: Optional country filter
        division_01_only: If True, filter to COICOP Division 01 only

    Returns:
        Tuple of (prepared DataFrame, validation stats)
    """
    print("\n" + "=" * 60)
    print("DATA LOADING")
    print("=" * 60)

    # Load
    df = load_price_data(filepath, country=country, division_01_only=division_01_only)

    # Validate
    df, stats = validate_price_data(df)

    # Prepare
    df = prepare_for_cpi(df)

    print("=" * 60 + "\n")

    return df, stats


def get_coicop_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """
    Get mapping of COICOP codes to titles.

    Args:
        df: Price DataFrame with coicop_code and coicop_title columns

    Returns:
        DataFrame with unique COICOP codes and their titles
    """
    if "coicop_title" not in df.columns:
        return pd.DataFrame(columns=["coicop_code", "coicop_3digit", "coicop_title"])

    mapping = (
        df[["coicop_code", "coicop_3digit", "coicop_title"]]
        .drop_duplicates()
        .sort_values("coicop_code")
    )

    return mapping


def summarize_data(df: pd.DataFrame) -> dict:
    """
    Generate summary statistics for the prepared data.

    Args:
        df: Prepared price DataFrame

    Returns:
        Dictionary with summary statistics
    """
    summary = {
        "total_observations": len(df),
        "unique_articles": df["url_hash"].nunique(),
        "unique_months": df["month"].nunique(),
        "month_range": (df["month"].min(), df["month"].max()),
        "coicop_3digit_categories": df["coicop_3digit"].nunique(),
        "coicop_4digit_categories": df["coicop_code"].nunique(),
        "countries": df["country"].unique().tolist() if "country" in df.columns else [],
        "sources": df["source"].unique().tolist() if "source" in df.columns else [],
    }

    # Observations per month
    obs_per_month = df.groupby("month").size()
    summary["obs_per_month_mean"] = obs_per_month.mean()
    summary["obs_per_month_min"] = obs_per_month.min()
    summary["obs_per_month_max"] = obs_per_month.max()

    # Articles per 3-digit COICOP
    articles_per_coicop = df.groupby("coicop_3digit")["url_hash"].nunique()
    summary["articles_per_coicop_mean"] = articles_per_coicop.mean()
    summary["articles_per_coicop_min"] = articles_per_coicop.min()
    summary["articles_per_coicop_max"] = articles_per_coicop.max()

    return summary
