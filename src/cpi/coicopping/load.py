"""Incremental load stage for the COICOP pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from typing import cast

from .data_preparation import prepare_coicop_matching_data_from_df
from .loading import (
    add_date_column,
    apply_latest_scrapy_mappings,
    get_currency_mapping,
    get_price_scraping_root,
    load_scrapy_data,
    load_wayback_data,
)
from .manifest import load_manifest, save_manifest, list_scrapy_files, list_wayback_dirs
from .utils import get_project_root


def _ensure_cache_schema(df_cache: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    if df_cache.empty:
        return df_new

    cache_cols = list(df_cache.columns)
    for col in cache_cols:
        if col not in df_new.columns:
            df_new[col] = None
    extra_cols = [col for col in df_new.columns if col not in cache_cols]
    ordered_cols = cache_cols + extra_cols
    return cast(pd.DataFrame, df_new.loc[:, ordered_cols].copy())


def _ensure_dataframe(value: pd.DataFrame | pd.Series) -> pd.DataFrame:
    if isinstance(value, pd.Series):
        return value.to_frame()
    return value


def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "product_id" in df.columns:
        df["product_id"] = df["product_id"].astype("string")
    return df


def run_load(project_root: Path, rebuild: bool = False) -> None:
    data_dir = project_root / "data" / "cpi" / "coicopping"
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "manifest.json"
    cache_path = data_dir / "prepared_cache.parquet"

    if rebuild or not cache_path.exists():
        if cache_path.exists():
            cache_path.unlink()
        if manifest_path.exists():
            manifest_path.unlink()

        print("Loading full dataset (rebuild mode)...")
        from .loading import load_price_scraping_data

        df_full = load_price_scraping_data(project_root=project_root)
        df_prepared = prepare_coicop_matching_data_from_df(df_full, project_root)
        df_prepared = _normalize_for_parquet(df_prepared)
        df_prepared.to_parquet(cache_path, index=False)

        root_dir = get_price_scraping_root(project_root)
        manifest = {
            "processed_scrapy_files": list_scrapy_files(root_dir),
            "processed_wayback_dirs": list_wayback_dirs(root_dir),
        }
        save_manifest(manifest_path, manifest)
        print(f"✓ Prepared cache saved to {cache_path}")
        print(f"✓ Manifest saved to {manifest_path}")
        return

    manifest = load_manifest(manifest_path)
    root_dir = get_price_scraping_root(project_root)
    all_scrapy_files = set(list_scrapy_files(root_dir))
    all_wayback_dirs = set(list_wayback_dirs(root_dir))

    processed_scrapy = set(manifest.get("processed_scrapy_files", []))
    processed_wayback = set(manifest.get("processed_wayback_dirs", []))

    new_scrapy_files = all_scrapy_files - processed_scrapy
    new_wayback_dirs = all_wayback_dirs - processed_wayback

    if not new_scrapy_files and not new_wayback_dirs:
        print("✓ No new scraping files detected. Cache unchanged.")
        return

    df_scrapy_new, processed_scrapy_files = load_scrapy_data(
        project_root=project_root,
        allowlist=new_scrapy_files,
    )

    cache_scrapy = pd.DataFrame()
    if cache_path.exists():
        try:
            cache_scrapy = pd.read_parquet(
                cache_path,
                columns=[
                    "wayback",
                    "url_hash",
                    "product_name",
                    "category",
                    "currency",
                    "country",
                    "source",
                ],
            )
            cache_scrapy = cache_scrapy[cache_scrapy["wayback"] == 0].copy()
        except Exception:
            cache_scrapy = pd.DataFrame()

    combined_scrapy = (
        pd.concat([cache_scrapy, df_scrapy_new], ignore_index=True)
        if not df_scrapy_new.empty or not cache_scrapy.empty
        else pd.DataFrame()
    )
    combined_scrapy = _ensure_dataframe(combined_scrapy)
    combined_scrapy_df = cast(pd.DataFrame, combined_scrapy)

    currency_mapping = (
        get_currency_mapping(combined_scrapy_df) if not combined_scrapy_df.empty else {}
    )

    df_wayback_new, processed_wayback_dirs = load_wayback_data(
        project_root=project_root,
        currency_mapping=currency_mapping,
        allowlist_dirs=new_wayback_dirs,
    )

    if not df_wayback_new.empty and not combined_scrapy_df.empty:
        df_wayback_new = apply_latest_scrapy_mappings(
            df_wayback_new, combined_scrapy_df
        )

    if df_scrapy_new.empty and df_wayback_new.empty:
        manifest["processed_scrapy_files"] = sorted(
            processed_scrapy | set(processed_scrapy_files)
        )
        manifest["processed_wayback_dirs"] = sorted(
            processed_wayback | set(processed_wayback_dirs)
        )
        save_manifest(manifest_path, manifest)
        print("✓ No new rows loaded (files were empty). Manifest updated.")
        return

    df_new = pd.concat([df_scrapy_new, df_wayback_new], ignore_index=True)
    df_new = add_date_column(df_new)
    df_prepared_new = prepare_coicop_matching_data_from_df(df_new, project_root)
    df_prepared_new = _normalize_for_parquet(df_prepared_new)

    df_cache = pd.read_parquet(cache_path) if cache_path.exists() else pd.DataFrame()
    if not df_cache.empty:
        df_cache = _normalize_for_parquet(df_cache)
    if df_cache.empty:
        df_cache = df_prepared_new
    else:
        df_prepared_new = _ensure_cache_schema(df_cache, df_prepared_new)
        df_cache = pd.concat([df_cache, df_prepared_new], ignore_index=True)

    df_cache.to_parquet(cache_path, index=False)

    manifest["processed_scrapy_files"] = sorted(
        processed_scrapy | set(processed_scrapy_files)
    )
    manifest["processed_wayback_dirs"] = sorted(
        processed_wayback | set(processed_wayback_dirs)
    )
    save_manifest(manifest_path, manifest)

    print(f"✓ Loaded {len(df_prepared_new)} new records")
    print(f"✓ Prepared cache updated: {cache_path}")
    print(f"✓ Manifest updated: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incremental load stage for COICOP pipeline"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild prepared cache and manifest from scratch",
    )

    args = parser.parse_args()
    project_root = get_project_root()

    try:
        run_load(project_root, rebuild=args.rebuild)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
