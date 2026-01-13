"""
Utility functions for loading and using human-readable labels.

This module provides functions to load labels from labels.json and apply them
to DataFrames for better readability in reports and dashboards.
"""

import json
from pathlib import Path
from typing import Dict, Optional
import pandas as pd


def load_labels(labels_file: Optional[Path] = None) -> Dict:
    """
    Load labels from labels.json file.

    Args:
        labels_file: Path to labels.json file. If None, uses default location.

    Returns:
        Dictionary containing all label mappings

    Example:
        >>> labels = load_labels()
        >>> labels['countries']['fiji']
        'Fiji'
        >>> labels['metrics']['n_obs']
        'Number of Observations'
    """
    if labels_file is None:
        labels_file = Path(__file__).parent / "labels.json"

    with open(labels_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_country_label(country_code: str, labels: Optional[Dict] = None) -> str:
    """
    Get human-readable label for a country code.

    Args:
        country_code: Country code (e.g., 'fiji', 'samoa')
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        Human-readable country name

    Example:
        >>> get_country_label('fiji')
        'Fiji'
    """
    if labels is None:
        labels = load_labels()

    return labels.get("countries", {}).get(
        country_code, country_code.replace("_", " ").title()
    )


def get_source_label(source_code: str, labels: Optional[Dict] = None) -> str:
    """
    Get human-readable label for a source/supermarket code.

    Args:
        source_code: Source code (e.g., 'rbpatel', 'mh_online')
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        Human-readable source name

    Example:
        >>> get_source_label('rbpatel')
        'RB Patel'
    """
    if labels is None:
        labels = load_labels()

    return labels.get("supermarkets", {}).get(
        source_code, source_code.replace("_", " ").title()
    )


def get_metric_label(metric_code: str, labels: Optional[Dict] = None) -> str:
    """
    Get human-readable label for a metric.

    Args:
        metric_code: Metric code (e.g., 'n_obs', 'share_items')
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        Human-readable metric name

    Example:
        >>> get_metric_label('n_obs')
        'Number of Observations'
    """
    if labels is None:
        labels = load_labels()

    return labels.get("metrics", {}).get(
        metric_code, metric_code.replace("_", " ").title()
    )


def get_column_label(column_code: str, labels: Optional[Dict] = None) -> str:
    """
    Get human-readable label for a column name.

    Args:
        column_code: Column code (e.g., 'url_hash', 'unit_value')
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        Human-readable column name

    Example:
        >>> get_column_label('url_hash')
        'URL Hash'
    """
    if labels is None:
        labels = load_labels()

    return labels.get("columns", {}).get(
        column_code, column_code.replace("_", " ").title()
    )


def add_country_labels(
    df: pd.DataFrame,
    country_column: str = "country",
    label_column: str = "country_label",
    labels: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Add human-readable country labels to a DataFrame.

    Args:
        df: DataFrame containing country codes
        country_column: Name of the column containing country codes
        label_column: Name of the column to create for labels
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        DataFrame with added label column
    """
    if country_column not in df.columns:
        return df

    if labels is None:
        labels = load_labels()

    df = df.copy()
    df[label_column] = df[country_column].apply(lambda x: get_country_label(x, labels))

    return df


def add_source_labels(
    df: pd.DataFrame,
    source_column: str = "source",
    label_column: str = "source_label",
    labels: Optional[Dict] = None,
) -> pd.DataFrame:
    """
    Add human-readable source labels to a DataFrame.

    Args:
        df: DataFrame containing source codes
        source_column: Name of the column containing source codes
        label_column: Name of the column to create for labels
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        DataFrame with added label column
    """
    if source_column not in df.columns:
        return df

    if labels is None:
        labels = load_labels()

    df = df.copy()
    df[label_column] = df[source_column].apply(lambda x: get_source_label(x, labels))

    return df


def rename_columns_with_labels(
    df: pd.DataFrame, labels: Optional[Dict] = None
) -> pd.DataFrame:
    """
    Rename DataFrame columns to human-readable labels.

    Args:
        df: DataFrame to rename
        labels: Pre-loaded labels dictionary. If None, loads from file.

    Returns:
        DataFrame with renamed columns

    Example:
        >>> df = pd.DataFrame({'n_obs': [100], 'n_items': [50]})
        >>> rename_columns_with_labels(df)
           Number of Observations  Number of Unique Items
        0                     100                      50
    """
    if labels is None:
        labels = load_labels()

    # Try to map columns from both 'columns' and 'metrics' sections
    column_mapping = {}
    for col in df.columns:
        if col in labels.get("columns", {}):
            column_mapping[col] = labels["columns"][col]
        elif col in labels.get("metrics", {}):
            column_mapping[col] = labels["metrics"][col]

    if column_mapping:
        df = df.rename(columns=column_mapping)

    return df


if __name__ == "__main__":
    # Test the functions
    print("Testing label functions...")

    # Load labels
    labels = load_labels()
    print(f"\nLoaded {len(labels)} label categories")

    # Test country labels
    print("\nCountry labels:")
    for code in ["fiji", "samoa", "vanuatu"]:
        print(f"  {code}: {get_country_label(code, labels)}")

    # Test source labels
    print("\nSource labels:")
    for code in ["rbpatel", "mh_online", "samoa_market"]:
        print(f"  {code}: {get_source_label(code, labels)}")

    # Test metric labels
    print("\nMetric labels:")
    for code in ["n_obs", "n_items", "share_items"]:
        print(f"  {code}: {get_metric_label(code, labels)}")

    # Test DataFrame labeling
    print("\nTesting DataFrame labeling:")
    test_df = pd.DataFrame(
        {
            "country": ["fiji", "samoa"],
            "source": ["rbpatel", "samoa_market"],
            "n_obs": [100, 200],
            "n_items": [50, 75],
        }
    )
    print("\nOriginal DataFrame:")
    print(test_df)

    # Add labels
    test_df = add_country_labels(test_df, labels=labels)
    test_df = add_source_labels(test_df, labels=labels)
    print("\nWith label columns:")
    print(test_df)

    # Rename columns
    test_df2 = test_df[["n_obs", "n_items"]].copy()
    test_df2 = rename_columns_with_labels(test_df2, labels=labels)
    print("\nWith renamed columns:")
    print(test_df2)
