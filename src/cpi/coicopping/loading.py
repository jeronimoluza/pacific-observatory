"""
Load price scraping data from JSONL files into a single dataframe.

The data is organized as:
data/cpi/price_scraping/{country}/{source}/raw_items/{source}_YYYYMMDD_HHMMSS.jsonl

This module reads all JSONL files and combines them into a single dataframe,
adding country, source, and filename columns.
"""

import json
from pathlib import Path
from typing import Optional

import pandas as pd


def get_price_scraping_root(project_root: Optional[Path] = None) -> Path:
    """
    Get the root directory for price scraping data.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        Path to data/cpi/price_scraping directory.
    """
    if project_root is None:
        # Infer from this file's location: src/cpi/coicopping/loading.py
        project_root = Path(__file__).parent.parent.parent.parent

    return project_root / "data" / "cpi" / "price_scraping"


def load_price_scraping_data(project_root: Optional[Path] = None) -> pd.DataFrame:
    """
    Load all price scraping data from JSONL files into a single dataframe.

    Reads all JSONL files from data/cpi/price_scraping/{country}/{source}/raw_items/
    and combines them into a single dataframe with added columns for country, source,
    and filename.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with all price data and metadata columns (country, source, filename).
    """
    root_dir = get_price_scraping_root(project_root)

    if not root_dir.exists():
        raise FileNotFoundError(f"Price scraping directory not found: {root_dir}")

    all_data = []

    # Iterate through country directories
    for country_dir in sorted(root_dir.iterdir()):
        if not country_dir.is_dir():
            continue

        country = country_dir.name

        # Iterate through source directories
        for source_dir in sorted(country_dir.iterdir()):
            if not source_dir.is_dir():
                continue

            source = source_dir.name
            raw_items_dir = source_dir / "raw_items"

            if not raw_items_dir.exists():
                continue

            # Iterate through JSONL files
            for jsonl_file in sorted(raw_items_dir.glob("*.jsonl")):
                filename = jsonl_file.name

                # Read JSONL file
                records = []
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            try:
                                record = json.loads(line)
                                record["country"] = country
                                record["source"] = source
                                record["filename"] = filename
                                records.append(record)
                            except json.JSONDecodeError as e:
                                print(
                                    f"Warning: Failed to parse line in {jsonl_file}: {e}"
                                )
                                continue

                if records:
                    all_data.extend(records)

    if not all_data:
        raise ValueError("No price scraping data found")

    df = pd.DataFrame(all_data)
    return df


if __name__ == "__main__":
    df = load_price_scraping_data()
    print(df.tail(10))
