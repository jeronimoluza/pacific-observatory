"""
Shared utilities for CPI construction.

Common functions used across the CPI analysis modules.
"""

import numpy as np
import pandas as pd
from typing import Optional


def extract_month(date_series: pd.Series) -> pd.Series:
    """
    Extract year-month string from datetime series.

    Args:
        date_series: Series of datetime values or strings

    Returns:
        Series with format 'YYYY-MM'
    """
    dt = pd.to_datetime(date_series)
    return dt.dt.to_period("M").astype(str)


def coicop_4digit_to_3digit(coicop_code: str) -> str:
    """
    Map 4-digit COICOP code to its 3-digit parent category.

    Examples:
        '01.1.1.3' -> '01.1.1'
        '01.1.2.5' -> '01.1.2'
        '01.2.1' -> '01.2.1' (already 3-digit, unchanged)

    Args:
        coicop_code: COICOP code string (e.g., '01.1.1.3')

    Returns:
        3-digit COICOP code (e.g., '01.1.1')
    """
    if pd.isna(coicop_code):
        return None

    parts = str(coicop_code).split(".")
    if len(parts) >= 4:
        # 4-digit code: take first 3 parts
        return ".".join(parts[:3])
    elif len(parts) == 3:
        # Already 3-digit
        return coicop_code


def coicop_to_2digit(coicop_code: str) -> str:
    """
    Map COICOP code to its 2-digit parent category.

    Examples:
        '01.1.1.3' -> '01.1'
        '01.1.2.5' -> '01.1'
        '01.2.1' -> '01.2'
        '01.1' -> '01.1' (already 2-digit, unchanged)

    Args:
        coicop_code: COICOP code string (e.g., '01.1.1.3')

    Returns:
        2-digit COICOP code (e.g., '01.1')
    """
    if pd.isna(coicop_code):
        return None

    parts = str(coicop_code).split(".")
    if len(parts) >= 2:
        # Take first 2 parts
        return ".".join(parts[:2])
    else:
        # Less than 2 parts, return as-is
        return coicop_code


def coicop_to_1digit(coicop_code: str) -> str:
    """
    Map COICOP code to its 1-digit division (top-level category).

    Examples:
        '01.1.1.3' -> '01'
        '01.1.2.5' -> '01'
        '02.1.1' -> '02'
        '01' -> '01' (already 1-digit, unchanged)

    Args:
        coicop_code: COICOP code string (e.g., '01.1.1.3')

    Returns:
        1-digit COICOP code (e.g., '01')
    """
    if pd.isna(coicop_code):
        return None

    parts = str(coicop_code).split(".")
    if len(parts) >= 1:
        # Take first part only
        return parts[0]
    else:
        return coicop_code


def is_division_01(coicop_code: str) -> bool:
    """
    Check if COICOP code belongs to Division 01 (Food and non-alcoholic beverages).

    Args:
        coicop_code: COICOP code string

    Returns:
        True if code starts with '01.'
    """
    if pd.isna(coicop_code):
        return False
    return str(coicop_code).startswith("01.")


def parse_price(price_str: str) -> Optional[float]:
    """
    Parse price string to float, handling currency symbols.

    Examples:
        '$7.99' -> 7.99
        '737VT' -> 737.0
        '7.99' -> 7.99

    Args:
        price_str: Price string with optional currency symbol

    Returns:
        Float price value or None if parsing fails
    """
    if pd.isna(price_str):
        return None

    price_str = str(price_str)

    # Remove common currency symbols and letters
    import re

    # Extract numeric part (including decimal)
    match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def geometric_mean(values: pd.Series) -> float:
    """
    Calculate geometric mean of a series.

    Uses log transformation: exp(mean(log(x)))

    Args:
        values: Series of positive numeric values

    Returns:
        Geometric mean
    """
    # Filter out non-positive values
    positive_values = values[values > 0]
    if len(positive_values) == 0:
        return np.nan

    return np.exp(np.log(positive_values).mean())


def validate_coicop_code(code: str) -> bool:
    """
    Validate COICOP code format.

    Valid formats: XX.X.X, XX.X.X.X, XX.X

    Args:
        code: COICOP code string

    Returns:
        True if valid format
    """
    if pd.isna(code):
        return False

    import re

    pattern = r"^\d{2}(\.\d+){1,3}$"
    return bool(re.match(pattern, str(code)))
