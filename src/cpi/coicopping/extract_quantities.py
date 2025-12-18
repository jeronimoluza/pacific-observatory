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
from unit_conversions import UNIT_CONVERSIONS


def parse_price(price_str) -> Optional[float]:
    """
    Parse a price string to extract the numeric value as a float.

    Handles formats like:
    - "$18.91 NZD Incl. VAGST"
    - "$20.99"
    - "15.00 K"
    - "18.91"
    - Already numeric values

    Args:
        price_str: The price value (string or numeric).

    Returns:
        The price as a float, or None if parsing fails.
    """
    import re

    # If already a float or int, return as float
    if isinstance(price_str, (int, float)):
        return float(price_str) if not pd.isna(price_str) else None

    # If not a string, return None
    if not isinstance(price_str, str):
        return None

    # Remove common currency symbols and text
    cleaned = price_str.strip()

    # Extract the first numeric value (with optional decimal)
    match = re.search(r"[\d,]+\.?\d*", cleaned)
    if not match:
        return None

    # Get the matched number and remove commas
    number_str = match.group().replace(",", "")

    try:
        return float(number_str)
    except (ValueError, TypeError):
        return None


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
            # Pattern: (range_val1, range_val2, range_unit) | (single_val, single_unit)
            (
                range_val1,
                range_val2,
                range_unit,
                single_val,
                single_unit,
            ) = amount_matches[0]
            if range_val1 and range_val2:
                # It's a range (e.g., "9-15kg" or "9kg-15kg"), use the average rounded down
                avg_value = int((float(range_val1) + float(range_val2)) / 2)
                amount = f"{avg_value} {range_unit}"
            elif single_val:
                # Single value (e.g., "9kg")
                amount = f"{single_val} {single_unit}"

    # Try to find units pattern (count) if not already found
    if units is None:
        units_matches = UNITS_REGEX.findall(product_name)
        if units_matches:
            # Use the first match found
            # Pattern: (range_val1, range_val2, range_unit) | (single_val, single_unit)
            range_val1, range_val2, range_unit, single_val, single_unit = units_matches[
                0
            ]
            if range_val1 and range_val2:
                # It's a range (e.g., "6-10 pack" or "6 pack-10 pack"), use the average rounded down
                avg_value = int((float(range_val1) + float(range_val2)) / 2)
                units = str(avg_value)
            elif single_val:
                # Single value (e.g., "6 pack")
                units = single_val

    # If no quantity specified, default units to "1"
    if units is None:
        units = "1"

    return amount, units


def calculate_unit_value(
    price, amount: Optional[str], units: Optional[str]
) -> Optional[float]:
    """
    Calculate the unit value (price per kg, lt, or mt) for a product.

    Logic:
        1. Parse the price string to extract numeric value
        2. Parse the amount string to extract numeric value and unit (e.g., "100 g" -> 100, "g")
        3. Convert the amount to standard units (kg, lt, mt) using UNIT_CONVERSIONS
        4. Parse the units string to get the count (e.g., "6" -> 6)
        5. Calculate: unit_value = price / (converted_amount * count)
        6. If no convertible amount unit, calculate: unit_value = price / count

    Args:
        price: The product price (string or numeric).
        amount: The amount string (e.g., "100 g", "1 kg", "500 ml") or None.
        units: The units count string (e.g., "6", "1") or None.

    Returns:
        The unit value (price per kg/lt/mt) or price per unit if no amount, or None if invalid.
        Returns as float (e.g., 10.00 not $10.00).
    """
    import re

    # Parse price to float
    price_float = parse_price(price)

    # Handle invalid price
    if price_float is None or price_float <= 0:
        return None

    # Parse units count (default to 1)
    try:
        count = int(float(units)) if units and not pd.isna(units) else 1
        if count <= 0:
            count = 1
    except (ValueError, TypeError):
        count = 1

    # If no amount, unit_value = price / count
    if amount is None or pd.isna(amount) or amount == "":
        return float(price_float / count)

    # Parse amount string to extract numeric value and unit
    amount_match = re.match(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", str(amount).strip())
    if not amount_match:
        return float(price_float / count)

    amount_value_str, amount_unit = amount_match.groups()

    try:
        amount_value = float(amount_value_str)
        if amount_value <= 0:
            return float(price_float / count)
    except (ValueError, TypeError):
        return float(price_float / count)

    # If no unit found, unit_value = price / count
    if not amount_unit:
        return float(price_float / count)

    # Convert to standard unit (kg, lt, mt)
    amount_unit_lower = amount_unit.lower()
    if amount_unit_lower not in UNIT_CONVERSIONS:
        # Unknown unit, just return price / count
        return float(price_float / count)

    conversion_factor, standard_unit = UNIT_CONVERSIONS[amount_unit_lower]

    # Convert amount to standard unit
    converted_amount = amount_value * conversion_factor

    # Total amount = converted_amount * count
    total_amount = converted_amount * count

    if total_amount <= 0:
        return None

    # unit_value = price / total_amount (price per kg, lt, or mt)
    unit_value = float(price_float / total_amount)

    return unit_value


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
        - unit_value (price per kg, lt, or mt; or price/units if no amount)
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

    # Calculate unit_value (price per kg, lt, or mt)
    df["unit_value"] = df.apply(
        lambda row: calculate_unit_value(row["price"], row["amount"], row["units"]),
        axis=1,
    ).astype("float64")

    # Rename 'url' to 'product_url' if it exists
    if "url" in df.columns and "product_url" not in df.columns:
        df = df.rename(columns={"url": "product_url"})

    # Select and order the required columns
    required_columns = [
        "product_name",
        "price",
        "amount",
        "units",
        "unit_value",
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
    print("\nUnit value statistics:")
    print(df["unit_value"].describe())
    df.to_csv("quantities.csv", index=False)
