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

New in standardized unit price system:
- Multi-candidate extraction: captures ALL quantity expressions
- Usability classification: classifies each product into tiered statuses
- Extraction tiers: Tier 1 (weight/volume), Tier 2 (count), Tier 3 (per-item)
- Promotion detection: flags promotional/bundle products
- No silent fallbacks: unresolved products have unit_value=None

Example:
- "maltesers fun size share pack chocolate 11 pack 132g" → amount = "132 g", units = "11 pack"
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# Handle both relative and direct execution
try:
    # from .loading import load_price_scraping_data
    from .prestep import prepare_coicop_matching_data
    from .cleaning import clean_product_names
except ImportError:
    # Direct execution: add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent))
    from prestep import prepare_coicop_matching_data
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

# Import new standardized unit price modules
from quantity_candidates import extract_all_candidates
from usability_classifier import (
    classify_usability,
    get_standard_unit,
    get_extraction_tier,
    UsabilityStatus,
)
from promotion_detection import detect_promotion


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
    price,
    amount: Optional[str],
    units: Optional[str],
    usability_status: Optional[str] = None,
) -> Optional[float]:
    """
    Calculate the unit value (price per kg, lt, or mt) for a product.

    IMPORTANT: This function now respects usability_status. Products that are
    not resolved (UNRESOLVED, PROMOTION_OR_BUNDLE, AMBIGUOUS_QUANTITY, UNIT_ONLY_NON_FOOD)
    will return None to avoid silent fallback behavior.

    Logic:
        1. Check usability_status - return None for non-resolved products
        2. Parse the price string to extract numeric value
        3. Parse the amount string to extract numeric value and unit (e.g., "100 g" -> 100, "g")
        4. Convert the amount to standard units (kg, lt, mt) using UNIT_CONVERSIONS
        5. Parse the units string to get the count (e.g., "6" -> 6)
        6. Calculate: unit_value = price / (converted_amount * count)
        7. For count-only food products: unit_value = price / count

    Args:
        price: The product price (string or numeric).
        amount: The amount string (e.g., "100 g", "1 kg", "500 ml") or None.
        units: The units count string (e.g., "6", "1") or None.
        usability_status: The usability classification status. If provided and not
                         resolved, returns None instead of computing a fallback value.

    Returns:
        The unit value (price per kg/lt/mt) or price per unit if no amount, or None if invalid.
        Returns as float (e.g., 10.00 not $10.00).
        Returns None for non-resolved products to avoid silent fallbacks.
    """
    import re

    # Check usability status - return None for non-resolved products
    # This prevents silent fallback behavior
    resolved_statuses = {
        UsabilityStatus.RESOLVED_WEIGHT_VOLUME.value,
        UsabilityStatus.RESOLVED_COUNT.value,
        UsabilityStatus.RESOLVED_PER_ITEM.value,
        UsabilityStatus.PENDING_REVIEW.value,
    }

    if usability_status is not None and usability_status not in resolved_statuses:
        # Non-resolved product - do not compute unit value
        return None

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

    # For per-item products (Tier 3), unit_value = price
    if usability_status == UsabilityStatus.RESOLVED_PER_ITEM.value:
        return float(price_float)

    # For count products (Tier 2), unit_value = price / count
    if usability_status == UsabilityStatus.RESOLVED_COUNT.value:
        return float(price_float / count)

    # If no amount, return None (no silent fallback for resolved mass/volume/length)
    if amount is None or pd.isna(amount) or amount == "":
        # Only return price/count if explicitly resolved as count food
        # Otherwise, this shouldn't happen for resolved mass/volume/length
        return None

    # Parse amount string to extract numeric value and unit
    amount_match = re.match(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?", str(amount).strip())
    if not amount_match:
        return None

    amount_value_str, amount_unit = amount_match.groups()

    try:
        amount_value = float(amount_value_str)
        if amount_value <= 0:
            return None
    except (ValueError, TypeError):
        return None

    # If no unit found, return None
    if not amount_unit:
        return None

    # Convert to standard unit (kg, lt, mt)
    amount_unit_lower = amount_unit.lower()
    if amount_unit_lower not in UNIT_CONVERSIONS:
        # Unknown unit - return None (no silent fallback)
        return None

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


def _extract_with_new_system(row: pd.Series) -> pd.Series:
    """
    Extract quantities using the new standardized system.

    This function performs multi-candidate extraction and classification
    for a single product row.

    Args:
        row: DataFrame row with at least 'product_name' column.
             Optionally 'coicop_code' for food detection.

    Returns:
        Series with: amount, units, usability_status, extraction_tier,
                    standard_unit, n_candidates, has_promotion, rejection_reason,
                    pending_review
    """
    product_name = row.get("product_name", "")
    coicop_code = row.get("coicop_code", None)

    # Extract all candidates
    extraction_result = extract_all_candidates(product_name)

    # Check for per_kg and per_each patterns first (backward compatibility)
    if isinstance(product_name, str):
        if PER_KG_REGEX.search(product_name):
            extraction_result.raw_amount = "1 kg"
            extraction_result.raw_units = None
        elif PER_EACH_REGEX.search(product_name):
            extraction_result.raw_amount = None
            extraction_result.raw_units = "1"

    # Classify usability
    usability_status, rejection_reason = classify_usability(
        extraction_result, product_name, coicop_code
    )

    # Get standard unit
    standard_unit = get_standard_unit(extraction_result, usability_status)

    # Check for promotion
    has_promotion, _ = detect_promotion(product_name)

    return pd.Series(
        {
            "amount": extraction_result.raw_amount,
            "units": extraction_result.raw_units
            if extraction_result.raw_units
            else "1",
            "usability_status": usability_status.value,
            "extraction_tier": get_extraction_tier(usability_status),
            "standard_unit": standard_unit,
            "n_candidates": extraction_result.n_candidates,
            "has_promotion": has_promotion,
            "rejection_reason": rejection_reason,
            "pending_review": False,  # TODO: implement review flagging logic
        }
    )


def extract_quantities(
    df_prepared: Optional[pd.DataFrame] = None, project_root: Optional[Path] = None
) -> pd.DataFrame:
    """
    Extract quantities from prepared product data using the standardized unit price system.

    This function now uses multi-candidate extraction and usability classification
    to provide high-quality unit prices suitable for inflation monitoring and
    cross-country analysis.

    Args:
        df_prepared: Optional pre-prepared DataFrame from prepare_coicop_matching_data().
                    If None, will call prepare_coicop_matching_data() internally.
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with columns:
        - product_name (clean)
        - price
        - amount
        - units
        - unit_value (price per kg, lt, mt, or per unit; None for non-resolved)
        - usability_status (classification: resolved_weight_volume, resolved_count, etc.)
        - extraction_tier (1, 2, or 3 indicating extraction quality tier)
        - standard_unit (kg, lt, mt, count, or None)
        - n_candidates (number of quantity expressions found)
        - has_promotion (boolean: promotional product detected)
        - rejection_reason (why not resolved, for diagnostics)
        - pending_review (boolean: flagged for manual review)
        - source
        - country
        - product_url
        - url_hash
    """
    # Use provided DataFrame or prepare data
    if df_prepared is None:
        df = prepare_coicop_matching_data(project_root)
        df = clean_product_names(df, project_root)
    else:
        # Data is already prepared and cleaned
        df = df_prepared.copy()

    # Extract quantities using the new standardized system
    new_columns = df.apply(_extract_with_new_system, axis=1)

    # Merge new columns into the DataFrame
    df = pd.concat([df, new_columns], axis=1)

    # Calculate unit_value respecting usability status
    # Only resolved products get a unit_value; others get None
    df["unit_value"] = df.apply(
        lambda row: calculate_unit_value(
            row["price"],
            row["amount"],
            row["units"],
            row["usability_status"],
        ),
        axis=1,
    ).astype("float64")

    # Rename 'url' to 'product_url' if it exists
    if "url" in df.columns and "product_url" not in df.columns:
        df = df.rename(columns={"url": "product_url"})

    # Select and order the required columns (including new columns)
    required_columns = [
        "product_name",
        "product_w_cat",
        "price",
        "currency",
        "amount",
        "units",
        "unit_value",
        "usability_status",
        "extraction_tier",
        "standard_unit",
        "n_candidates",
        "has_promotion",
        "rejection_reason",
        "pending_review",
        "source",
        "country",
        "product_url",
        "url_hash",
        "date",
        "scraped_at",
        "wayback",
    ]

    # Add optional columns if they exist
    optional_columns = ["product_id"]
    for col in optional_columns:
        if col in df.columns:
            required_columns.append(col)

    # Check if all required columns exist
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        # Print available columns for debugging
        print(f"Available columns: {df.columns.tolist()}")
        raise KeyError(f"Missing columns in data: {missing_columns}")

    df_result = df[required_columns].copy()

    return df_result


def merge_quantities_with_gemini(
    df_quantities: pd.DataFrame,
    gemini_classification_path: Path,
) -> pd.DataFrame:
    """
    Merge quantities DataFrame with COICOP classifications from gemini_classification.csv.

    Merges on url_hash and product_w_cat keys, adds date column, and sorts by url_hash and date.

    Args:
        df_quantities: DataFrame with extracted quantities
        gemini_classification_path: Path to gemini_classification.csv file

    Returns:
        Merged DataFrame with COICOP classifications sorted by url_hash and date,
        or original df_quantities if file doesn't exist
    """
    if not gemini_classification_path.exists():
        print(
            f"\n⚠ gemini_classification.csv not found at {gemini_classification_path}"
        )
        print("Skipping merge step")
        # Add empty COICOP columns
        df_quantities["coicop_code"] = None
        df_quantities["coicop_title"] = None
        return df_quantities

    print("\nLoading gemini_classification.csv...")
    df_gemini = pd.read_csv(gemini_classification_path)
    print(f"✓ Loaded {len(df_gemini)} classified products")

    # Merge quantities with gemini_classification using url_hash
    # This ensures all items (scrapy and wayback) with the same url_hash get the same classification
    print("\nMerging quantities with COICOP classifications...")
    print("  Merge key: url_hash")

    # Group by url_hash and keep first classification (most recent)
    # This handles cases where same url_hash has multiple product_w_cat values
    df_gemini_unique = df_gemini.drop_duplicates(subset=["url_hash"], keep="first")
    print(f"  Using {len(df_gemini_unique)} unique url_hash classifications")

    # Merge on url_hash only to ensure all items with same url_hash get classified
    df_merged = df_quantities.merge(
        df_gemini_unique[["url_hash", "coicop_code", "coicop_title"]],
        on="url_hash",
        how="left",
        suffixes=("", "_gemini"),
    )

    print(f"✓ Merged data: {len(df_merged)} records")

    # Sort by url_hash and date (date should already exist from loading.py)
    if "date" in df_merged.columns:
        # Convert to timezone-naive to avoid comparison issues
        # Handle both tz-aware and tz-naive timestamps
        df_merged["date"] = pd.to_datetime(df_merged["date"], utc=True).dt.tz_localize(
            None
        )
        df_merged = df_merged.sort_values(by=["url_hash", "date"], na_position="last")
        print("✓ Sorted by url_hash and date")
    else:
        print("⚠ Warning: 'date' column not found, skipping sort")

    # Print merge summary
    classified = df_merged["coicop_code"].notna().sum()
    unclassified = df_merged["coicop_code"].isna().sum()
    print("\nMerge summary:")
    print(f"  - Total records: {len(df_merged)}")
    print(f"  - Classified: {classified}")
    print(f"  - Unclassified: {unclassified}")

    # Print usability status distribution
    if "usability_status" in df_merged.columns:
        print("\nUsability status distribution:")
        status_counts = df_merged["usability_status"].value_counts()
        for status, count in status_counts.items():
            pct = count / len(df_merged) * 100
            print(f"  - {status}: {count} ({pct:.1f}%)")

        # Calculate resolved rate
        resolved_statuses = [
            "resolved_weight_volume",
            "resolved_count",
            "resolved_per_item",
        ]
        resolved_count = df_merged[
            df_merged["usability_status"].isin(resolved_statuses)
        ].shape[0]
        resolved_pct = resolved_count / len(df_merged) * 100
        print(f"\n  Total resolved: {resolved_count} ({resolved_pct:.1f}%)")

    return df_merged


def extract_and_merge_quantities(
    project_root: Optional[Path] = None,
    gemini_classification_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Extract quantities from price scraping data and merge with COICOP classifications.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.
        gemini_classification_path: Optional path to gemini_classification.csv. If None, skips merge.

    Returns:
        DataFrame with extracted quantities, optionally merged with COICOP classifications
    """
    print("\n" + "=" * 70)
    print("Extracting quantities from price scraping data...")
    print("=" * 70)

    df_quantities = extract_quantities(project_root)
    print(f"✓ Extracted quantities for {len(df_quantities)} products")

    if gemini_classification_path is None:
        return df_quantities

    return merge_quantities_with_gemini(df_quantities, gemini_classification_path)


if __name__ == "__main__":
    # Get project root
    project_root = Path(__file__).parent.parent.parent.parent
    data_dir = project_root / "data" / "cpi" / "coicopping"
    gemini_classification_path = data_dir / "gemini_classification.csv"

    # Extract quantities and merge with COICOP classifications
    df = extract_and_merge_quantities(
        project_root=project_root,
        gemini_classification_path=gemini_classification_path,
    )

    print(f"\n✓ Final dataset: {len(df)} products")
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

    # Save to CSV
    output_path = data_dir / "unit_values_w_categories.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
