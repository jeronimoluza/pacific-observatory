"""
Extract quantities (amounts and units) from product names using regex patterns.

This module reads price scraping data, cleans product names, and extracts
quantity information (amount and units) from the cleaned product names.

The extraction uses regex patterns to identify:
- Amounts: g, gm, kg, lb, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm
- Units: can, cans, pack, packs, piece, pieces, pcs

Special cases:
- If per_kg_regex matches: amount = "1 kg", units = NaN
- If per_each_regex matches: amount = NaN, units = "1"
- If no regex matches: amount = NaN, units = NaN
"""

import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# Handle both relative and direct execution
try:
    from .loading import load_price_scraping_data
    from .cleaning import clean_product_names
except ImportError:
    # Direct execution: add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent))
    from loading import load_price_scraping_data
    from cleaning import clean_product_names


# Regex patterns for quantity extraction
QUANTITY_REGEX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(g|gm|kg|lb|oz|ml|mls|l|litre|ltrs|ltr|gallon|gal|m|cm|can|cans|pack|packs|piece|pieces|pcs)\b",
    re.IGNORECASE
)

# Regex to find "(per/kg)" or "(per kg)" variations
PER_KG_REGEX = re.compile(r'\(per\s*/\s*kg\)|\(per\s*kg\)', re.IGNORECASE)

# Regex to find "(per/each)" or "(per each)" variations
PER_EACH_REGEX = re.compile(r'\(per\s*/\s*each\)|\(per\s*each\)', re.IGNORECASE)


def extract_amount_and_units(product_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract amount and units from a product name using regex patterns.

    Args:
        product_name: The product name to extract quantities from.

    Returns:
        Tuple of (amount, units) where each can be a string or NaN.
        
    Logic:
        - If quantity_regex matches: extract amount and units
        - Else if per_kg_regex matches: amount = "1 kg", units = NaN
        - Else if per_each_regex matches: amount = NaN, units = "1"
        - Else: amount = NaN, units = NaN
    """
    if not isinstance(product_name, str):
        return None, None

    # Try to find quantity pattern (amount + unit)
    matches = QUANTITY_REGEX.findall(product_name)
    if matches:
        # Use the first match found
        value1, value2, unit = matches[0]
        if value2:
            # It's a range, use the first value
            amount = f"{value1} {unit}"
        else:
            amount = f"{value1} {unit}"
        return amount, None

    # Check for per_kg pattern
    if PER_KG_REGEX.search(product_name):
        return "1 kg", None

    # Check for per_each pattern
    if PER_EACH_REGEX.search(product_name):
        return None, "1"

    # No match found
    return None, None


def extract_quantities(project_root: Optional[Path] = None) -> pd.DataFrame:
    """
    Load price scraping data, clean product names, and extract quantities.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with columns:
        - product_name (clean)
        - price
        - amount
        - units
        - source
        - country
        - product_url
    """
    # Load raw price scraping data
    df = load_price_scraping_data(project_root)

    # Clean product names
    df = clean_product_names(df, project_root)

    # Extract amount and units
    df[['amount', 'units']] = df['product_name'].apply(
        lambda x: pd.Series(extract_amount_and_units(x))
    )

    # Rename 'url' to 'product_url' if it exists
    if 'url' in df.columns and 'product_url' not in df.columns:
        df = df.rename(columns={'url': 'product_url'})

    # Select and order the required columns
    required_columns = ['product_name', 'price', 'amount', 'units', 'source', 'country', 'product_url']

    # Check if all required columns exist
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        # Print available columns for debugging
        print(f"Available columns: {df.columns.tolist()}")
        raise KeyError(f"Missing columns in data: {missing_columns}")

    df_result = df[required_columns].copy()

    return df_result


if __name__ == "__main__":
    # Example usage
    df = extract_quantities()
    print(f"Extracted quantities for {len(df)} products")
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nFirst 10 rows:")
    print(df.head(10))
    print(f"\nData types:")
    print(df.dtypes)
    print(f"\nAmount and units distribution:")
    print(f"Amount value counts:\n{df['amount'].value_counts().head(10)}")
    print(f"\nUnits value counts:\n{df['units'].value_counts().head(10)}")
