"""
Load price scraping data from JSONL files into a single dataframe.

The data is organized as:
data/cpi/price_scraping/{country}/{source}/raw_items/{source}_YYYYMMDD_HHMMSS.jsonl

This module reads all JSONL files and combines them into a single dataframe,
adding country, source, and filename columns.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
UTC_TZ = ZoneInfo("UTC")


def _to_utc_from_ba(dt: datetime) -> datetime:
    localized = dt.replace(tzinfo=BA_TZ)
    return localized.astimezone(UTC_TZ)


def _parse_scraped_at_utc(scraped_at: str) -> Optional[str]:
    if not scraped_at:
        return None
    try:
        parsed = pd.to_datetime(scraped_at)
    except Exception:
        return None

    if isinstance(parsed, pd.Timestamp):
        parsed = parsed.to_pydatetime()

    if not isinstance(parsed, datetime):
        return None

    return _to_utc_from_ba(parsed).isoformat()


def _parse_filename_timestamp(filename: str) -> Optional[str]:
    stem = Path(filename).stem
    if len(stem) < 15:
        return None
    ts = stem[-15:]
    try:
        parsed = datetime.strptime(ts, "%Y%m%d_%H%M%S")
    except Exception:
        return None
    return _to_utc_from_ba(parsed).isoformat()


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


def get_currency_mapping(df_scrapy: pd.DataFrame) -> dict:
    """
    Extract currency mapping from scrapy data by country and source.

    For each (country, source) combination, finds the most common currency value.
    This mapping is then applied to wayback data which may not have currency info.

    Args:
        df_scrapy: DataFrame with scrapy data containing country, source, and currency columns

    Returns:
        Dictionary mapping (country, source) tuples to currency codes
        Example: {('fiji', 'mh_online'): 'FJ', ('samoa', 'samoa_market'): 'WST'}
    """
    currency_mapping = {}

    if df_scrapy.empty or "currency" not in df_scrapy.columns:
        return currency_mapping

    # Group by country and source, find most common currency
    for (country, source), group in df_scrapy.groupby(["country", "source"]):
        # Get most common currency for this country/source combination
        currency_counts = group["currency"].value_counts()
        if len(currency_counts) > 0:
            most_common_currency = currency_counts.index[0]
            currency_mapping[(country, source)] = most_common_currency
    return currency_mapping


def load_scrapy_data(
    project_root: Optional[Path] = None,
    allowlist: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """
    Load scrapy JSONL files from raw_items directories.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        Tuple of (DataFrame with scrapy data and metadata columns, processed file list).
    """
    root_dir = get_price_scraping_root(project_root)

    if not root_dir.exists():
        logger.warning(f"Price scraping directory not found: {root_dir}")
        result_df = pd.DataFrame()
        return result_df, []

    all_data = []
    processed_files: list[str] = []

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
                rel_path = jsonl_file.relative_to(root_dir).as_posix()
                if allowlist is not None and rel_path not in allowlist:
                    continue
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
                                record["wayback"] = 0  # Mark as current data

                                if "scraped_at_utc" not in record:
                                    scraped_at_utc = _parse_scraped_at_utc(
                                        record.get("scraped_at")
                                    )
                                    if not scraped_at_utc:
                                        scraped_at_utc = _parse_filename_timestamp(
                                            filename
                                        )
                                    if scraped_at_utc:
                                        record["scraped_at_utc"] = scraped_at_utc
                                records.append(record)
                            except json.JSONDecodeError as e:
                                logger.warning(
                                    f"Failed to parse line in {jsonl_file}: {e}"
                                )
                                continue

                if records:
                    all_data.extend(records)
                processed_files.append(rel_path)

    if not all_data:
        logger.warning("No scrapy data found")
        result_df = pd.DataFrame()
        return result_df, processed_files

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} scrapy records")
    if "scraped_at_utc" in df.columns:
        missing = df["scraped_at_utc"].isna().sum()
        logger.info(f"scraped_at_utc missing: {missing}")
    else:
        logger.warning("scraped_at_utc column missing from scrapy data")
    return df, processed_files


def load_wayback_data(
    project_root: Optional[Path] = None,
    currency_mapping: Optional[dict] = None,
    allowlist_dirs: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """
    Load wayback machine JSON files from wayback_machine_data/items directories.

    Applies currency mapping from scrapy data to wayback records that may not have currency info.

    Args:
        project_root: Optional project root path. If None, infers from this file's location.
        currency_mapping: Dictionary mapping (country, source) tuples to currency codes.
                         If None, wayback data will not have currency applied.

    Returns:
        Tuple of (DataFrame with wayback data and metadata columns, processed dir list).
    """
    root_dir = get_price_scraping_root(project_root)

    if not root_dir.exists():
        logger.warning(f"Price scraping directory not found: {root_dir}")
        result_df = pd.DataFrame()
        return result_df, []

    all_data = []
    processed_dirs: list[str] = []

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
            wayback_items_dir = source_dir / "wayback_machine_data" / "items"
            rel_dir = wayback_items_dir.relative_to(root_dir).as_posix()

            if allowlist_dirs is not None and rel_dir not in allowlist_dirs:
                continue

            if not wayback_items_dir.exists():
                continue

            # Find JSON files
            json_files = list(wayback_items_dir.glob("*.json"))
            if not json_files:
                continue

            processed_dirs.append(rel_dir)

            # Get currency for this country/source combination
            currency = None
            if currency_mapping and (country, source) in currency_mapping:
                currency = currency_mapping[(country, source)]

            # Load all JSON files
            for json_file in json_files:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        snapshots = json.load(f)
                        if isinstance(snapshots, list):
                            for snapshot in snapshots:
                                # Add metadata columns
                                snapshot["country"] = country
                                snapshot["source"] = source
                                snapshot["wayback"] = 1  # Mark as wayback data

                                # Apply currency mapping if available and not already present
                                if currency and "currency" not in snapshot:
                                    snapshot["currency"] = currency
                                elif currency and pd.isna(snapshot.get("currency")):
                                    snapshot["currency"] = currency

                                # Use wayback_url as product_url for wayback items
                                if "wayback_url" in snapshot and "url" not in snapshot:
                                    snapshot["url"] = snapshot["wayback_url"]

                                all_data.append(snapshot)
                        else:
                            logger.warning(
                                f"Expected list in {json_file}, got {type(snapshots)}"
                            )
                except Exception as e:
                    logger.error(f"Error reading {json_file}: {e}")
                    continue

    if not all_data:
        logger.warning("No wayback data found")
        result_df = pd.DataFrame()
        return result_df, processed_dirs

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} wayback records")

    return df, processed_dirs


def apply_latest_scrapy_mappings(
    df_wayback: pd.DataFrame, df_scrapy: pd.DataFrame
) -> pd.DataFrame:
    if df_wayback.empty or df_scrapy.empty:
        return df_wayback

    product_name_mapping = {}
    if "url_hash" in df_scrapy.columns and "product_name" in df_scrapy.columns:
        for url_hash, group in df_scrapy.groupby("url_hash"):
            latest_product_name = group["product_name"].iloc[-1]
            if pd.notna(latest_product_name):
                product_name_mapping[url_hash] = latest_product_name

    category_mapping = {}
    if "url_hash" in df_scrapy.columns and "category" in df_scrapy.columns:
        for url_hash, group in df_scrapy.groupby("url_hash"):
            latest_category = group["category"].iloc[-1]
            if pd.notna(latest_category):
                category_mapping[url_hash] = latest_category

    if "url_hash" in df_wayback.columns:
        if product_name_mapping:
            mask = df_wayback["url_hash"].isin(list(product_name_mapping.keys()))
            df_wayback.loc[mask, "product_name"] = df_wayback.loc[mask, "url_hash"].map(
                product_name_mapping
            )

        if category_mapping:
            mask = df_wayback["url_hash"].isin(list(category_mapping.keys()))
            df_wayback.loc[mask, "category"] = df_wayback.loc[mask, "url_hash"].map(
                category_mapping
            )

    return df_wayback


def add_date_column(df: pd.DataFrame) -> pd.DataFrame:
    def extract_date(row):
        scraped_at_utc = row.get("scraped_at_utc")
        if pd.notna(scraped_at_utc):
            try:
                return pd.to_datetime(scraped_at_utc, utc=True).tz_convert(None)
            except Exception:
                return pd.NaT
        if pd.notna(row.get("wayback_timestamp")):
            ts = str(row["wayback_timestamp"])
            try:
                return pd.to_datetime(ts, format="%Y%m%d%H%M%S")
            except Exception:
                return pd.NaT
        if pd.notna(row.get("scraped_at")):
            return pd.to_datetime(row["scraped_at"])
        return pd.NaT

    df = df.copy()
    df["date"] = df.apply(extract_date, axis=1)
    logger.info(
        f"Added date column: {df['date'].notna().sum()} records with valid dates"
    )
    df = df.dropna(subset=["price"])
    return df


def load_price_scraping_data(project_root: Optional[Path] = None) -> pd.DataFrame:
    """
    Load all price scraping data from JSONL and JSON files into a single dataframe.

    Combines:
    - Scrapy JSONL files from raw_items/
    - Wayback JSON files from wayback_machine_data/items/

    Applies currency mapping from scrapy data to wayback data for each country/source combination.

    Ensures product_name and category consistency by using the latest scrapy values for all wayback data:
    - Groups scrapy items by url_hash and keeps the last occurrence for product_name and category
    - Creates mapping dictionaries from these latest values
    - Applies these mappings to wayback data to replace product_name and category

    Args:
        project_root: Optional project root path. If None, infers from this file's location.

    Returns:
        DataFrame with all price data and metadata columns (country, source, wayback, date, currency).
    """
    logger.info("Loading price scraping data...")

    # Load scrapy data first
    df_scrapy, _ = load_scrapy_data(project_root=project_root)

    # Create currency mapping from scrapy data
    currency_mapping = {}
    if not df_scrapy.empty:
        currency_mapping = get_currency_mapping(df_scrapy)

    # Load wayback data with currency mapping applied
    df_wayback, _ = load_wayback_data(
        project_root=project_root,
        currency_mapping=currency_mapping,
    )

    # Combine both datasets
    if df_scrapy.empty and df_wayback.empty:
        raise ValueError("No price scraping data found (neither scrapy nor wayback)")

    if df_scrapy.empty:
        logger.info("No scrapy data found, using wayback data only")
        df = df_wayback
    elif df_wayback.empty:
        logger.info("No wayback data found, using scrapy data only")
        df = df_scrapy
    else:
        logger.info(
            "Creating product_name and category mappings from latest scrapy items..."
        )
        df_wayback = apply_latest_scrapy_mappings(df_wayback, df_scrapy)
        logger.info("Applied product_name and category mappings to wayback data")

        # Combine both
        df = pd.concat([df_scrapy, df_wayback], ignore_index=True)
        logger.info(
            f"Combined {len(df_scrapy)} scrapy + {len(df_wayback)} wayback = {len(df)} total records"
        )

    df = add_date_column(df)
    return df


if __name__ == "__main__":
    df = load_price_scraping_data()
    print(df.tail(10))
