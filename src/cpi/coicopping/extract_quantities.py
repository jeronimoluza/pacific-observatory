"""
Extract quantities (amounts and units) from product names using regex patterns.

This module reads price scraping data, cleans product names, and extracts
quantity information (amount and units) from the cleaned product names.

The extraction uses regex patterns to identify:
- Amount (weight/volume): g, gm, kg, lb, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm
- Units (count): can, cans, pack, packs, piece, pieces, pcs

Special cases:
- If per_kg_regex matches: amount = "1 kg", units = NaN
- If per_each_regex matches: amount = NaN, units = "1"
- If no quantity specified: amount = NaN, units = "1" (default unit is 1)

Example:
- "maltesers fun size share pack chocolate 11 pack 132g" → amount = "132 g", units = "11 pack"
"""

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


from regex_config import (
    AMOUNT_REGEX,
    UNITS_REGEX,
    X_SEPARATOR_REGEX,
    PER_KG_REGEX,
    PER_EACH_REGEX,
    COUNT_UNITS,
    AMOUNT_UNITS,
)


def extract_amount_and_units(product_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract amount and units from a product name using regex patterns.

    Args:
        product_name: The product name to extract quantities from.

    Returns:
        Tuple of (amount, units) where each can be a string or NaN.

    Logic:
        1. Check for per_kg pattern first: amount = "1 kg", units = None
        2. Check for per_each pattern: amount = None, units = "1"
        3. Look for x-separator patterns (e.g., "30 x 105g", "3g x 2000", "x 500")
        4. Extract amount (weight/volume): g, gm, kg, lb, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm
        5. Extract units (count): can, cans, pack, packs, piece, pieces, pcs
        6. If no quantity specified: amount = None, units = "1" (default unit is 1)
    """
    if not isinstance(product_name, str):
        return None, "1"

    amount = None
    units = None

    # Check for per_kg pattern first (takes priority)
    if PER_KG_REGEX.search(product_name):
        amount = "1 kg"
        units = None
        return amount, units

    # Check for per_each pattern (takes priority)
    if PER_EACH_REGEX.search(product_name):
        amount = None
        units = "1"
        return amount, units

    # Try to find x-separator patterns (e.g., "30 x 105g", "3g x 2000", "x 500", "28 x 6pack", "250mls x 24")
    x_sep_matches = X_SEPARATOR_REGEX.findall(product_name)
    if x_sep_matches:
        # Process x-separator matches to determine if it's amount or units
        for first_num, first_unit, second_num, second_unit in x_sep_matches:
            # Check if first side has an amount unit (e.g., "250mls x 24")
            if first_unit and first_unit.lower() in COUNT_UNITS:
                # First side is a count unit, skip this match (handled by UNITS_REGEX)
                continue
            elif first_unit and first_unit.lower() in AMOUNT_UNITS:
                # First side is an amount unit (e.g., "250mls x 24")
                if amount is None:
                    amount = f"{first_num} {first_unit}"
                # Second number is the units count
                if units is None:
                    units = second_num
            # Check if second side has a unit
            elif second_unit:
                # Second side has a unit suffix (e.g., "x 105g", "x 6pack")
                if second_unit.lower() in COUNT_UNITS:
                    # This is a count unit (e.g., "6pack" means 6 packs)
                    # first_num is items per pack, second_num is number of packs
                    # Total units = first_num * second_num
                    if first_num and units is None:
                        try:
                            total_units = int(float(first_num) * float(second_num))
                            units = str(total_units)
                        except (ValueError, TypeError):
                            units = first_num
                else:
                    # This is a weight/volume unit (e.g., "x 105g") -> second_num is the amount
                    if amount is None:
                        amount = f"{second_num} {second_unit}"
                    # first_num is the units count (if present)
                    if first_num and units is None:
                        units = first_num
            else:
                # No unit suffix (e.g., "x 500", "x 2000") -> second_num is the units
                if units is None:
                    units = second_num

    # Try to find amount pattern (weight/volume) if not already found
    if amount is None:
        amount_matches = AMOUNT_REGEX.findall(product_name)
        if amount_matches:
            # Use the first match found
            value1, value2, unit = amount_matches[0]
            if value2:
                # It's a range, use the first value
                amount = f"{value1} {unit}"
            else:
                amount = f"{value1} {unit}"

    # Try to find units pattern (count) if not already found
    if units is None:
        units_matches = UNITS_REGEX.findall(product_name)
        if units_matches:
            # Use the first match found
            value1, value2, unit = units_matches[0]
            if value2:
                # It's a range, use the first value
                units = value1
            else:
                units = value1

    # If no quantity specified, default units to "1"
    if units is None:
        units = "1"

    return amount, units


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
        - url_hash
    """
    # Load raw price scraping data
    df = load_price_scraping_data(project_root)

    # Clean product names
    df = clean_product_names(df, project_root)

    # Extract amount and units
    df[["amount", "units"]] = df["product_name"].apply(
        lambda x: pd.Series(extract_amount_and_units(x))
    )

    # Rename 'url' to 'product_url' if it exists
    if "url" in df.columns and "product_url" not in df.columns:
        df = df.rename(columns={"url": "product_url"})

    # Select and order the required columns
    required_columns = [
        "product_name",
        "price",
        "amount",
        "units",
        "source",
        "country",
        "product_url",
        "url_hash",
    ]

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
    print("\nFirst 10 rows:")
    print(df.head(10))
    print("\nData types:")
    print(df.dtypes)
    print("\nAmount and units distribution:")
    print(f"Amount value counts:\n{df['amount'].value_counts().head(10)}")
    print(f"\nUnits value counts:\n{df['units'].value_counts().head(10)}")
    df.to_csv("quantities.csv", index=False)
