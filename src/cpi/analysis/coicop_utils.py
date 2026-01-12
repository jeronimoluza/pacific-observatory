"""
Utility functions for loading and mapping COICOP codes to titles.

This module provides functions to load COICOP categories from the UN Stats Excel file
and create mappings between COICOP codes and their descriptive titles.
"""

from pathlib import Path
from typing import Dict, Optional
import pandas as pd

# Import from coicopping module
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from coicopping.coicop_categories import get_coicop_categories


def load_coicop_mapping(
    digit_level: int = 4, data_dir: Optional[Path] = None
) -> Dict[str, str]:
    """
    Load COICOP code to title mapping from Excel file.

    Args:
        digit_level: Number of dots in COICOP code (digit level). Defaults to 4.
        data_dir: Directory where coicop_categories.xlsx is stored.
                 Defaults to data/cpi/coicopping relative to project root.

    Returns:
        Dictionary mapping COICOP codes to titles

    Example:
        >>> mapping = load_coicop_mapping(digit_level=4)
        >>> mapping['01.1.1.1']
        'Bread'
    """
    df = get_coicop_categories(data_dir=data_dir, digit_level=digit_level)

    # Create mapping from coicop_code to coicop_title
    mapping = dict(zip(df["coicop_code"], df["coicop_title"]))

    return mapping


def load_all_coicop_levels(
    data_dir: Optional[Path] = None,
) -> Dict[int, Dict[str, str]]:
    """
    Load COICOP mappings for all digit levels (1, 2, 3, 4).

    Args:
        data_dir: Directory where coicop_categories.xlsx is stored.

    Returns:
        Dictionary with keys 1, 2, 3, 4 containing code-to-title mappings

    Example:
        >>> mappings = load_all_coicop_levels()
        >>> mappings[1]['01']
        'Food and non-alcoholic beverages'
        >>> mappings[2]['01.1']
        'Food'
        >>> mappings[4]['01.1.1.1']
        'Bread'
    """
    mappings = {}
    for level in [1, 2, 3, 4]:
        mappings[level] = load_coicop_mapping(digit_level=level, data_dir=data_dir)

    return mappings


def add_coicop_titles(
    df: pd.DataFrame,
    code_column: str = "coicop_code",
    title_column: str = "coicop_title",
    data_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Add COICOP titles to a DataFrame based on COICOP codes.

    Args:
        df: DataFrame containing COICOP codes
        code_column: Name of the column containing COICOP codes
        title_column: Name of the column to create for titles
        data_dir: Directory where coicop_categories.xlsx is stored.

    Returns:
        DataFrame with added title column
    """
    if code_column not in df.columns:
        raise ValueError(f"Column '{code_column}' not found in DataFrame")

    # Determine digit level from the codes
    sample_code = df[code_column].dropna().iloc[0] if len(df) > 0 else None
    if sample_code is None:
        return df

    # Count dots to determine level
    n_dots = str(sample_code).count(".")
    digit_level = n_dots + 1

    # Load mapping for this level
    mapping = load_coicop_mapping(digit_level=digit_level, data_dir=data_dir)

    # Add titles
    df = df.copy()
    df[title_column] = df[code_column].map(mapping)

    return df


if __name__ == "__main__":
    # Test the functions
    print("Testing COICOP mapping functions...")

    # Test single level
    mapping_4 = load_coicop_mapping(digit_level=4)
    print(f"\nLoaded {len(mapping_4)} level-4 COICOP codes")
    print("Sample mappings:")
    for code, title in list(mapping_4.items())[:5]:
        print(f"  {code}: {title}")

    # Test all levels
    all_mappings = load_all_coicop_levels()
    print(f"\nLoaded mappings for {len(all_mappings)} levels:")
    for level, mapping in all_mappings.items():
        print(f"  Level {level}: {len(mapping)} codes")
