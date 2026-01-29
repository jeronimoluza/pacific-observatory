"""
Clean product names from price scraping data.

This module provides functions to clean product names by removing hardcoded
string values defined in string_cleaning.json configuration file.

The cleaning configuration is organized by source (e.g., aldi_au, dynamic_vanuatu)
and contains lists of strings to remove from product names.
"""

import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd


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


def get_string_cleaning_config(project_root: Optional[Path] = None) -> dict:
    """
    Load the string cleaning configuration from string_cleaning.json.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        Dictionary with source names as keys and lists of strings to remove as values.
        Example: {"aldi_au": ["string1", "string2"], "dynamic_vanuatu": ["stringA"]}

    Raises:
        FileNotFoundError: If string_cleaning.json is not found.
        json.JSONDecodeError: If string_cleaning.json is not valid JSON.
    """
    if project_root is None:
        # Infer from this file's location: src/cpi/coicopping/cleaning.py
        project_root = Path(__file__).parent.parent.parent.parent

    config_file = Path(__file__).parent / "config" / "string_cleaning.json"

    if not config_file.exists():
        raise FileNotFoundError(
            f"String cleaning configuration not found: {config_file}"
        )

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    return config


def clean_product_name(product_name: str, strings_to_remove: list) -> str:
    """
    Clean a product name by removing specified strings.

    Converts product_name to lowercase before applying string replacements.

    Args:
        product_name: The product name to clean.
        strings_to_remove: List of strings to remove from the product name.

    Returns:
        Cleaned product name (lowercase) with specified strings removed.
    """
    if not isinstance(product_name, str):
        return product_name

    # Convert to lowercase for case-insensitive matching
    cleaned = product_name.lower()

    for string in strings_to_remove:
        cleaned = cleaned.replace(string.lower(), "")

    # Clean up extra whitespace that may result from removals
    cleaned = " ".join(cleaned.split())

    return cleaned


def clean_special_characters(text: str) -> str:
    """
    Clean special characters from text by replacing them with spaces.

    Replaces any non-alphanumeric character (except spaces) with " ".
    Preserves Unicode letters and numbers from all languages.
    Then cleans up extra whitespace by stripping and joining words.

    Args:
        text: The text to clean.

    Returns:
        Text with special characters replaced by spaces and cleaned up.
    """

    if not isinstance(text, str):
        return text

    # Keep Unicode letters/numbers, replace punctuation with spaces
    cleaned = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)

    cleaned = " ".join(cleaned.split())
    return cleaned


def clean_product_names(
    df: pd.DataFrame, project_root: Optional[Path] = None
) -> pd.DataFrame:
    """
    Clean product names in a dataframe based on source-specific cleaning rules.

    Expects the dataframe to have 'product_name' and 'source' columns.
    Applies source-specific cleaning rules from string_cleaning.json.

    For samoa_market source, also applies product filtering via clean_samoa_market().

    Args:
        df: DataFrame with 'product_name' and 'source' columns.
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with cleaned product names. Original dataframe is not modified.

    Raises:
        KeyError: If 'product_name' or 'source' columns are missing.
        FileNotFoundError: If string_cleaning.json is not found.
    """
    if "product_name" not in df.columns:
        raise KeyError("DataFrame must contain 'product_name' column")

    if "source" not in df.columns:
        raise KeyError("DataFrame must contain 'source' column")

    # Load cleaning configuration
    config = get_string_cleaning_config(project_root)

    # Create a copy to avoid modifying the original dataframe
    df_cleaned = df.copy()

    df_cleaned["product_name"] = df_cleaned["product_name"].str.lower()

    # Apply source-specific cleaning rules
    for idx, row in df_cleaned.iterrows():
        source = row["source"]
        product_name = row["product_name"]

        # Get cleaning rules for this source, if they exist
        strings_to_remove = config.get(source, [])

        if strings_to_remove:
            df_cleaned.at[idx, "product_name"] = clean_product_name(
                product_name, strings_to_remove
            )

    # Apply samoa_market-specific product filtering
    samoa_market_mask = df_cleaned["source"] == "samoa_market"
    if samoa_market_mask.any():
        samoa_market_data = df_cleaned[samoa_market_mask]
        samoa_market_cleaned = clean_samoa_market(samoa_market_data)

        # Update samoa_market rows with filtered data
        df_cleaned = pd.concat(
            [df_cleaned[~samoa_market_mask], samoa_market_cleaned], ignore_index=True
        )

    return df_cleaned


def clean_samoa_market(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove specific product types and bracketed text from samoa_market data.

    Filters out products that match any of these patterns (case-insensitive):
    - "birthday combo #"
    - "aiga combo "
    - "voucher \"redeem at ah liki wholesale\""

    Also removes all bracketed text [...] that contains the word "avail".

    Args:
        df: DataFrame with 'product_name' column.

    Returns:
        DataFrame with filtered products and cleaned product names.
        Original dataframe is not modified.

    Raises:
        KeyError: If 'product_name' column is missing.
    """
    import re

    if "product_name" not in df.columns:
        raise KeyError("DataFrame must contain 'product_name' column")

    # Create a copy to avoid modifying the original dataframe
    df_filtered = df.copy()

    # Convert product names to lowercase for case-insensitive matching
    product_names_lower = df_filtered["product_name"].str.lower()

    # Create boolean mask for products to keep (inverse of patterns to remove)
    mask_keep = ~(
        product_names_lower.str.contains("birthday combo #", na=False)
        | product_names_lower.str.contains("aiga combo ", na=False)
        | product_names_lower.str.contains(
            'voucher "redeem at ah liki wholesale"', na=False
        )
    )

    # Filter dataframe to remove unwanted product types
    df_filtered = df_filtered[mask_keep].reset_index(drop=True)

    # Remove bracketed text containing "avail" from product names
    def remove_avail_brackets(product_name):
        """Remove all [...] that contain 'avail' (case-insensitive)."""
        if not isinstance(product_name, str):
            return product_name
        # Pattern: [anything containing 'avail' (case-insensitive)]
        cleaned = re.sub(
            r"\[[^\]]*avail[^\]]*\]", "", product_name, flags=re.IGNORECASE
        )
        # Clean up extra whitespace
        cleaned = " ".join(cleaned.split())
        return cleaned

    df_filtered["product_name"] = df_filtered["product_name"].apply(
        remove_avail_brackets
    )

    return df_filtered


if __name__ == "__main__":
    # Example usage
    from loading import load_price_scraping_data

    # Load raw data
    df = load_price_scraping_data()
    print(f"Loaded {len(df)} records")
    print(f"Columns: {df.columns.tolist()}")

    df["og_names"] = df["product_name"]
    # Clean product names
    df_cleaned = clean_product_names(df)
    print(f"\nCleaned {len(df_cleaned)} records")

    # Show sample of cleaned data
    print("\nSample of cleaned data:")
    print(df_cleaned[["source", "product_name"]].head(10))

    df_cleaned.product_name.to_csv("cleaned_product_names.csv", index=False)
