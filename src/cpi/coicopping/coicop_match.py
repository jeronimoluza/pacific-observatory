"""
Match products to COICOP categories using product names and categories.

This module reads price scraping data, cleans it, extracts product names without
quantities, and creates product-category combinations for COICOP matching.

The workflow:
1. Load and clean price scraping data
2. Remove amounts and quantities from product names → "product_only"
3. Clean "product_only" from special characters
4. Clean category names (lowercase, remove "Home " prefix, clean special chars)
5. Create "product_w_cat" combining product_only and cleaned category
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import re


# Handle both relative and direct execution
try:
    from .loading import load_price_scraping_data
    from .cleaning import clean_product_names, clean_special_characters
    from .regex_config import AMOUNT_REGEX, UNITS_REGEX, PER_KG_REGEX, PER_EACH_REGEX, COUNT_UNITS, STOPWORDS
except ImportError:
    # Direct execution: add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent))
    from loading import load_price_scraping_data
    from cleaning import clean_product_names, clean_special_characters
    from regex_config import AMOUNT_REGEX, UNITS_REGEX, PER_KG_REGEX, PER_EACH_REGEX, COUNT_UNITS, STOPWORDS



def clean_product_only(product_name: str) -> str:
    """
    Clean product name by removing all strings contained in () or [].

    Removes parentheses and brackets along with their contents.

    Args:
        product_name: The product name to clean.

    Returns:
        Product name with parentheses/brackets and their contents removed.
    """
    if not isinstance(product_name, str):
        return product_name

    # Remove content in parentheses: (...)
    cleaned = re.sub(r"\([^)]*\)", "", product_name)

    # Remove content in square brackets: [...]
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)

    # Clean up extra whitespace
    cleaned = " ".join(cleaned.split())

    return cleaned


def remove_amounts_and_quantities(product_name: str) -> str:
    """
    Remove amounts and quantities from a product name.

    Uses regex patterns to identify and remove:
    - Amount (weight/volume): g, gm, kg, lb, oz, ml, mls, l, litre, ltrs, ltr, gallon, gal, m, cm
    - Units (count): can, cans, pack, packs, piece, pieces, pcs
    - Per kg/each patterns

    Args:
        product_name: The product name to clean.

    Returns:
        Product name with amounts and quantities removed.
    """
    if not isinstance(product_name, str):
        return product_name

    cleaned = product_name

    # Remove amount patterns (weight/volume)
    cleaned = AMOUNT_REGEX.sub("", cleaned)

    # Remove units patterns (count)
    cleaned = UNITS_REGEX.sub("", cleaned)

    # Remove per kg pattern
    cleaned = PER_KG_REGEX.sub("", cleaned)

    # Remove per each pattern
    cleaned = PER_EACH_REGEX.sub("", cleaned)

    # Clean up extra whitespace that may result from removals
    cleaned = " ".join(cleaned.split())

    return cleaned


def clean_category(category: str) -> str:
    """
    Clean a category name for use in product-category combinations.

    Steps:
    1. Convert to lowercase
    2. Remove "Home " prefix if present (case-insensitive)
    3. Clean special characters (replace with ", ")

    Args:
        category: The category name to clean.

    Returns:
        Cleaned category name.
    """
    if not isinstance(category, str):
        return category

    # Convert to lowercase
    cleaned = category.lower()

    # Remove "Home" prefix (case-insensitive): handles "Home", "Home > category", etc.
    cleaned = re.sub(r"^home(?:\s*>\s*)?", "", cleaned, flags=re.IGNORECASE)

    # Clean special characters
    cleaned = clean_special_characters(cleaned)

    return cleaned


def create_product_with_category(product_only: str, category: str) -> str:
    """
    Create a product-category combination string.

    Format: "{product_only}; {cleaned_category}"

    Args:
        product_only: The product name without quantities.
        category: The category name (will be cleaned).

    Returns:
        Combined product-category string.
    """
    if not isinstance(product_only, str) or not isinstance(category, str):
        return ""

    cleaned_cat = clean_category(category)
    return f"{product_only}; {cleaned_cat}"


def clean_product_w_cat(text: str) -> str:
    """
    Clean product_w_cat strings by removing words with numbers, single characters, and stopwords.

    Cleaning steps (in order):
    1. Remove all words that contain any numbers (e.g., "123", "8x24s", "1235sw2", "92777a", "412w")
    2. Remove all words with len(word) == 1 (e.g., "x", "o", "c")
    3. Remove all stopwords (includes nltk stopwords, size words, count units, and additional packaging words)

    Args:
        text: The product_w_cat string to clean.

    Returns:
        Cleaned product_w_cat string with words separated by spaces.
    """
    if not isinstance(text, str):
        return text

    # Split text into words
    words = text.split()
    cleaned_words = []

    for word in words:
        # Step 1: Skip if word contains any digit
        if any(char.isdigit() for char in word):
            continue

        # Step 2: Skip if word is single character
        if len(word) == 1:
            continue

        # Step 3: Skip if word is in STOPWORDS (includes nltk stopwords + size words + count units + additional units)
        if word.lower() in STOPWORDS:
            continue

        # Keep the word if it passes all filters
        cleaned_words.append(word)

    # Join cleaned words back together
    cleaned_text = " ".join(cleaned_words)

    return cleaned_text


def prepare_coicop_matching_data(project_root: Optional[Path] = None) -> pd.DataFrame:
    """
    Load price scraping data and prepare it for COICOP matching.

    Steps:
    1. Load raw price scraping data
    2. Clean product names (source-specific cleaning)
    3. Remove amounts and quantities → "product_only"
    4. Clean "product_only" from special characters
    5. Clean category names
    6. Create "product_w_cat" combining product_only and cleaned category

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with columns:
        - product_name (cleaned)
        - product_only (no quantities)
        - product_w_cat (product_only + category)
        - category (original)
        - price
        - source
        - country
        - product_url (renamed from 'url' if exists)
        - url_hash
        - And any other original columns
    """
    # Load raw price scraping data
    df = load_price_scraping_data(project_root)

    # Clean product names (source-specific cleaning)
    df = clean_product_names(df, project_root)

    # Clean product names by removing content in parentheses and brackets
    df["product_name"] = df["product_name"].apply(clean_product_only)

    # Remove amounts and quantities from product names
    df["product_only"] = df["product_name"].apply(remove_amounts_and_quantities)

    # Clean product_only from special characters
    df["product_only"] = df["product_only"].apply(clean_special_characters)

    # Create product_w_cat combining product_only and cleaned category
    if "category" in df.columns:
        df["product_w_cat"] = df.apply(
            lambda row: (
                create_product_with_category(row["product_only"], row["category"])
                if pd.notna(row["category"]) and str(row["category"]).strip()
                else row["product_only"]
            ),
            axis=1,
        )
    else:
        # If no category column, product_w_cat is same as product_only
        df["product_w_cat"] = df["product_only"]

    # Clean product_w_cat by removing numbers, single characters, and stopwords
    df["product_w_cat"] = df["product_w_cat"].apply(clean_product_w_cat)

    # Rename 'url' to 'product_url' if it exists
    if "url" in df.columns and "product_url" not in df.columns:
        df = df.rename(columns={"url": "product_url"})

    return df


if __name__ == "__main__":
    # Example usage
    df = prepare_coicop_matching_data()
    print(f"Prepared {len(df)} products for COICOP matching")
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nFirst 10 rows:")
    print(df[["product_name", "product_only", "product_w_cat"]].head(10))
    print(f"\nData types:")
    print(df.dtypes)
    df[["product_name", "product_only", "category", "product_w_cat"]].to_csv("coicop_matching_data.csv", index=False)
