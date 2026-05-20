"""Load price scraping data into a single DataFrame.

The 4-level layout is:

    data/prices/{region}/{subregion}/{country}/{source}/
        raw_items/{source}_YYYYMMDD_HHMMSS.jsonl       # live scrapy
        wayback_items/{source}_YYYYMMDD_HHMMSS.jsonl   # backfill.py output
        wayback_items/.ledger.json                     # backfill resumability
        wayback_machine_data/items/{url_hash}.json     # LEGACY (stragglers only)
        common_crawl_data/items/{url_hash}.json        # cc_warc_fetcher output

Each loader returns a DataFrame plus the list of paths it processed (relative
to the prices root) so the caller can extend the incremental manifest.

Each row carries:
    country, source, region, subregion, source_kind, wayback (derived)
where ``source_kind`` is one of ``live | wayback | common_crawl | legacy_wmd``
and ``wayback`` is the legacy back-compat bool (``0`` iff ``source_kind ==
"live"``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
UTC_TZ = ZoneInfo("UTC")

# source_kind values that should be flagged with wayback=1 for back-compat.
_HISTORICAL_KINDS = {"wayback", "common_crawl", "legacy_wmd"}


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


def get_prices_data_root(project_root: Optional[Path] = None) -> Path:
    """Return the root directory for the new 4-level prices data tree."""
    if project_root is None:
        # src/prices/enrich/loading.py → project_root is four parents up.
        project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "data" / "prices"


def _iter_source_dirs(root_dir: Path) -> Iterable[Tuple[str, str, str, str, Path]]:
    """Yield (region, subregion, country, source, source_dir) tuples.

    Walks ``root_dir/{region}/{subregion}/{country}/{source}/``. Directories
    whose name starts with ``_`` (e.g. ``_enrich``) are skipped at every
    level so the enrichment tree itself doesn't get treated as a source.
    """
    if not root_dir.exists():
        return
    for region_dir in sorted(root_dir.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith("_"):
            continue
        for sub_dir in sorted(region_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                continue
            for country_dir in sorted(sub_dir.iterdir()):
                if not country_dir.is_dir() or country_dir.name.startswith("_"):
                    continue
                for source_dir in sorted(country_dir.iterdir()):
                    if not source_dir.is_dir() or source_dir.name.startswith("_"):
                        continue
                    yield (
                        region_dir.name,
                        sub_dir.name,
                        country_dir.name,
                        source_dir.name,
                        source_dir,
                    )


def _attach_kind(record: dict, source_kind: str) -> None:
    """Attach source_kind + the derived wayback bool to a record in-place."""
    record["source_kind"] = source_kind
    record["wayback"] = 1 if source_kind in _HISTORICAL_KINDS else 0


def get_currency_mapping(df_scrapy: pd.DataFrame) -> dict:
    """Map (country, source) → most-common currency from scrapy rows."""
    currency_mapping: dict = {}
    if df_scrapy.empty or "currency" not in df_scrapy.columns:
        return currency_mapping

    for (country, source), group in df_scrapy.groupby(["country", "source"]):
        currency_counts = group["currency"].value_counts()
        if len(currency_counts) > 0:
            currency_mapping[(country, source)] = currency_counts.index[0]
    return currency_mapping


def load_scrapy_data(
    project_root: Optional[Path] = None,
    allowlist: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """Walk ``raw_items/*.jsonl`` under each source. source_kind=``live``."""
    root_dir = get_prices_data_root(project_root)

    if not root_dir.exists():
        logger.warning(f"Prices data directory not found: {root_dir}")
        return pd.DataFrame(), []

    all_data: list[dict] = []
    processed_files: list[str] = []

    for region, sub, country, source, source_dir in _iter_source_dirs(root_dir):
        raw_items_dir = source_dir / "raw_items"
        if not raw_items_dir.exists():
            continue

        for jsonl_file in sorted(raw_items_dir.glob("*.jsonl")):
            rel_path = jsonl_file.relative_to(root_dir).as_posix()
            if allowlist is not None and rel_path not in allowlist:
                continue
            filename = jsonl_file.name

            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line in {jsonl_file}: {e}")
                        continue
                    record["country"] = country
                    record["source"] = source
                    record["region"] = region
                    record["subregion"] = sub
                    record["filename"] = filename
                    _attach_kind(record, "live")

                    if "scraped_at_utc" not in record:
                        scraped_at_utc = _parse_scraped_at_utc(
                            record.get("scraped_at")
                        )
                        if not scraped_at_utc:
                            scraped_at_utc = _parse_filename_timestamp(filename)
                        if scraped_at_utc:
                            record["scraped_at_utc"] = scraped_at_utc
                    all_data.append(record)
            processed_files.append(rel_path)

    if not all_data:
        logger.warning("No scrapy data found")
        return pd.DataFrame(), processed_files

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} scrapy (live) records")
    return df, processed_files


def load_wayback_items_data(
    project_root: Optional[Path] = None,
    currency_mapping: Optional[dict] = None,
    allowlist: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """Walk ``wayback_items/*.jsonl`` (new backfill format). source_kind=``wayback``.

    Each row in the JSONL already carries ``url_hash``, ``wayback_timestamp``,
    ``scraped_at_utc`` and ``source_kind="wayback"`` from backfill.py, so this
    loader only attaches region/subregion/country/source metadata.
    """
    root_dir = get_prices_data_root(project_root)

    if not root_dir.exists():
        return pd.DataFrame(), []

    all_data: list[dict] = []
    processed_files: list[str] = []

    for region, sub, country, source, source_dir in _iter_source_dirs(root_dir):
        wayback_dir = source_dir / "wayback_items"
        if not wayback_dir.exists():
            continue

        currency = (
            currency_mapping.get((country, source))
            if currency_mapping is not None
            else None
        )

        for jsonl_file in sorted(wayback_dir.glob("*.jsonl")):
            rel_path = jsonl_file.relative_to(root_dir).as_posix()
            if allowlist is not None and rel_path not in allowlist:
                continue

            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line in {jsonl_file}: {e}")
                        continue
                    record["country"] = country
                    record["source"] = source
                    record["region"] = region
                    record["subregion"] = sub
                    _attach_kind(record, "wayback")

                    if currency and not record.get("currency"):
                        record["currency"] = currency
                    if "wayback_url" in record and "url" not in record:
                        record["url"] = record["wayback_url"]
                    all_data.append(record)
            processed_files.append(rel_path)

    if not all_data:
        return pd.DataFrame(), processed_files

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} wayback (jsonl) records")
    return df, processed_files


def load_common_crawl_data(
    project_root: Optional[Path] = None,
    currency_mapping: Optional[dict] = None,
    allowlist_dirs: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """Walk ``common_crawl_data/items/*.json``. source_kind=``common_crawl``.

    Each file is named ``<url_hash>.json`` and contains a single dict with
    ``url``, ``cc_timestamp`` (YYYYMMDDHHMMSS), ``cc_index``, ``scraped_at``,
    ``product_name``, ``price``, etc. We project a ``wayback_timestamp``
    alias from ``cc_timestamp`` so downstream code that already understands
    that column can date these rows.
    """
    root_dir = get_prices_data_root(project_root)

    if not root_dir.exists():
        return pd.DataFrame(), []

    all_data: list[dict] = []
    processed_dirs: list[str] = []

    for region, sub, country, source, source_dir in _iter_source_dirs(root_dir):
        cc_items_dir = source_dir / "common_crawl_data" / "items"
        if not cc_items_dir.exists():
            continue
        rel_dir = cc_items_dir.relative_to(root_dir).as_posix()
        if allowlist_dirs is not None and rel_dir not in allowlist_dirs:
            continue

        json_files = list(cc_items_dir.glob("*.json"))
        if not json_files:
            continue

        currency = (
            currency_mapping.get((country, source))
            if currency_mapping is not None
            else None
        )

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    record = json.load(f)
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")
                continue

            if not isinstance(record, dict):
                logger.warning(f"Expected dict in {json_file}, got {type(record)}")
                continue

            record["country"] = country
            record["source"] = source
            record["region"] = region
            record["subregion"] = sub
            _attach_kind(record, "common_crawl")
            record.setdefault("url_hash", json_file.stem)

            cc_ts = record.get("cc_timestamp")
            if cc_ts and "wayback_timestamp" not in record:
                record["wayback_timestamp"] = cc_ts

            if currency and not record.get("currency"):
                record["currency"] = currency

            all_data.append(record)
        processed_dirs.append(rel_dir)

    if not all_data:
        return pd.DataFrame(), processed_dirs

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} common_crawl records")
    return df, processed_dirs


def load_legacy_wayback_machine_data(
    project_root: Optional[Path] = None,
    currency_mapping: Optional[dict] = None,
    allowlist_dirs: Optional[set[str]] = None,
) -> Tuple[pd.DataFrame, list[str]]:
    """Read legacy ``wayback_machine_data/items/*.json`` (pre-backfill format).

    TEMPORARY — only the two stragglers (``citysuper_hk`` /
    ``cold_storage_sg``) still rely on this. Delete this function once they
    are re-backfilled into ``wayback_items/``. source_kind=``legacy_wmd``.
    """
    root_dir = get_prices_data_root(project_root)

    if not root_dir.exists():
        return pd.DataFrame(), []

    all_data: list[dict] = []
    processed_dirs: list[str] = []

    for region, sub, country, source, source_dir in _iter_source_dirs(root_dir):
        items_dir = source_dir / "wayback_machine_data" / "items"
        if not items_dir.exists():
            continue
        rel_dir = items_dir.relative_to(root_dir).as_posix()
        if allowlist_dirs is not None and rel_dir not in allowlist_dirs:
            continue

        json_files = list(items_dir.glob("*.json"))
        if not json_files:
            continue
        logger.warning(
            f"Reading legacy wayback_machine_data for {country}/{source} "
            f"({len(json_files)} files). Re-backfill into wayback_items/ "
            "and delete this directory to drop legacy_wmd support."
        )

        processed_dirs.append(rel_dir)

        currency = (
            currency_mapping.get((country, source))
            if currency_mapping is not None
            else None
        )

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    snapshots = json.load(f)
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")
                continue
            if not isinstance(snapshots, list):
                logger.warning(f"Expected list in {json_file}, got {type(snapshots)}")
                continue

            for snapshot in snapshots:
                snapshot["country"] = country
                snapshot["source"] = source
                snapshot["region"] = region
                snapshot["subregion"] = sub
                _attach_kind(snapshot, "legacy_wmd")

                if currency and not snapshot.get("currency"):
                    snapshot["currency"] = currency
                if "wayback_url" in snapshot and "url" not in snapshot:
                    snapshot["url"] = snapshot["wayback_url"]
                all_data.append(snapshot)

    if not all_data:
        return pd.DataFrame(), processed_dirs

    df = pd.DataFrame(all_data)
    logger.info(f"Loaded {len(df)} legacy_wmd records")
    return df, processed_dirs


def apply_latest_scrapy_mappings(
    df_historical: pd.DataFrame, df_scrapy: pd.DataFrame
) -> pd.DataFrame:
    """Apply latest live-scrapy product_name + category onto historical rows."""
    if df_historical.empty or df_scrapy.empty:
        return df_historical

    product_name_mapping: dict = {}
    if "url_hash" in df_scrapy.columns and "product_name" in df_scrapy.columns:
        for url_hash, group in df_scrapy.groupby("url_hash"):
            latest_product_name = group["product_name"].iloc[-1]
            if pd.notna(latest_product_name):
                product_name_mapping[url_hash] = latest_product_name

    category_mapping: dict = {}
    if "url_hash" in df_scrapy.columns and "category" in df_scrapy.columns:
        for url_hash, group in df_scrapy.groupby("url_hash"):
            latest_category = group["category"].iloc[-1]
            if pd.notna(latest_category):
                category_mapping[url_hash] = latest_category

    if "url_hash" in df_historical.columns:
        if product_name_mapping:
            mask = df_historical["url_hash"].isin(list(product_name_mapping.keys()))
            df_historical.loc[mask, "product_name"] = df_historical.loc[
                mask, "url_hash"
            ].map(product_name_mapping)
        if category_mapping:
            mask = df_historical["url_hash"].isin(list(category_mapping.keys()))
            df_historical.loc[mask, "category"] = df_historical.loc[
                mask, "url_hash"
            ].map(category_mapping)

    return df_historical


def add_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Derive the canonical ``date`` column from per-row timestamps.

    Order of preference:
      1. ``scraped_at_utc``     (live + wayback rows)
      2. ``wayback_timestamp``  (wayback + common_crawl rows, YYYYMMDDHHMMSS)
      3. ``scraped_at``         (fallback when nothing else is present)
    """

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
    """Load every source (live + wayback + common_crawl + legacy_wmd) into one DataFrame."""
    logger.info("Loading price scraping data...")

    df_scrapy, _ = load_scrapy_data(project_root=project_root)

    currency_mapping = (
        get_currency_mapping(df_scrapy) if not df_scrapy.empty else {}
    )

    df_wayback, _ = load_wayback_items_data(
        project_root=project_root,
        currency_mapping=currency_mapping,
    )
    df_common_crawl, _ = load_common_crawl_data(
        project_root=project_root,
        currency_mapping=currency_mapping,
    )
    df_legacy_wmd, _ = load_legacy_wayback_machine_data(
        project_root=project_root,
        currency_mapping=currency_mapping,
    )

    historical_frames = [
        df for df in (df_wayback, df_common_crawl, df_legacy_wmd) if not df.empty
    ]
    df_historical = (
        pd.concat(historical_frames, ignore_index=True)
        if historical_frames
        else pd.DataFrame()
    )

    if df_scrapy.empty and df_historical.empty:
        raise ValueError("No price scraping data found")

    if df_scrapy.empty:
        df = df_historical
    elif df_historical.empty:
        df = df_scrapy
    else:
        df_historical = apply_latest_scrapy_mappings(df_historical, df_scrapy)
        df = pd.concat([df_scrapy, df_historical], ignore_index=True)
        logger.info(
            f"Combined {len(df_scrapy)} live + {len(df_historical)} historical "
            f"= {len(df)} total records"
        )

    df = add_date_column(df)
    return df


if __name__ == "__main__":
    df = load_price_scraping_data()
    print(df.tail(10))
