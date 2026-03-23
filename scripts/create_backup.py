#!/usr/bin/env python3
"""
Create a structured backup zip of scraped data.

Sections in the archive:
  text/                       <- news articles per country/newspaper
  retail-prices/              <- assembled supermarket price CSVs per country/source
  fuel-prices/                <- fuel price observations + source metadata

Usage:
    poetry run python scripts/create_backup.py
    poetry run python scripts/create_backup.py --path /path/to/output.zip
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Add src/ to path so we can import the fetcher registry
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from cpi.fuel_prices.fetchers import FETCHER_REGISTRY, FetcherConfig  # noqa: E402

# ── Repo layout ───────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_ROOT = REPO_ROOT / "data" / "text"
PRICE_SCRAPING_ROOT = REPO_ROOT / "data" / "cpi" / "price_scraping"
FUEL_PRICES_ROOT = REPO_ROOT / "data" / "cpi" / "fuel_prices"

RETAIL_COLUMNS = [
    "url_hash",
    "product_id",
    "product_name",
    "price",
    "currency",
    "category",
    "source",
    "country",
    "date",
    "wayback",
]


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    today = date.today().strftime("%Y%m%d")
    default_path = REPO_ROOT / f"backup-{today}.zip"
    parser = argparse.ArgumentParser(
        description="Backup text, retail-prices, and fuel-prices data into a zip archive."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=default_path,
        help=f"Output zip path (default: {default_path})",
    )
    return parser.parse_args()


# ── Text section ──────────────────────────────────────────────────────────────


def backup_text(zf: zipfile.ZipFile) -> int:
    """Copy data/text/{country}/{newspaper}/news.csv into text/ in the archive."""
    if not TEXT_ROOT.exists():
        print("[text] Root not found, skipping.", file=sys.stderr)
        return 0

    csv_files = sorted(TEXT_ROOT.glob("*/*/news.csv"))
    print(f"[text] Found {len(csv_files)} news.csv files")

    count = 0
    warnings: list[str] = []
    for csv_path in tqdm(csv_files, desc="text", unit="file"):
        try:
            rel = csv_path.relative_to(TEXT_ROOT)
            zf.write(csv_path, arcname=f"text/{rel}")
            count += 1
        except Exception as e:
            warnings.append(f"  WARN [{csv_path.name}]: {e}")
    for w in warnings:
        print(w, file=sys.stderr)
    return count


# ── Retail-prices section ─────────────────────────────────────────────────────


def _load_raw_items(source_dir: Path, country: str, source: str) -> pd.DataFrame:
    """Load live scrape JSONL files for one (country, source) pair."""
    raw_items_dir = source_dir / "raw_items"
    if not raw_items_dir.exists():
        return pd.DataFrame()

    records: list[dict] = []
    for jsonl_path in sorted(raw_items_dir.glob("*.jsonl")):
        with jsonl_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    rec["country"] = country
                    rec["source"] = source
                    rec["wayback"] = 0
                    rec["date"] = rec.get("scraped_at")
                    records.append(rec)
                except json.JSONDecodeError:
                    pass

    return pd.DataFrame(records) if records else pd.DataFrame()


def _load_wayback_items(source_dir: Path, country: str, source: str) -> pd.DataFrame:
    """Load Wayback Machine JSON snapshot files for one (country, source) pair."""
    wb_dir = source_dir / "wayback_machine_data" / "items"
    if not wb_dir.exists():
        return pd.DataFrame()

    records: list[dict] = []
    for json_path in sorted(wb_dir.glob("*.json")):
        try:
            with json_path.open(encoding="utf-8") as fh:
                snapshots = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(snapshots, list):
            continue
        for snap in snapshots:
            snap["country"] = country
            snap["source"] = source
            snap["wayback"] = 1
            ts = snap.get("wayback_timestamp", "")
            snap["date"] = ts if ts else snap.get("scraped_at")
            if "url" not in snap and "wayback_url" in snap:
                snap["url"] = snap["wayback_url"]
            records.append(snap)

    return pd.DataFrame(records) if records else pd.DataFrame()


def _assemble_source_prices(
    source_dir: Path, country: str, source: str
) -> pd.DataFrame:
    """Combine raw + wayback records for one source into a clean DataFrame."""
    df_raw = _load_raw_items(source_dir, country, source)
    df_wb = _load_wayback_items(source_dir, country, source)

    if df_raw.empty and df_wb.empty:
        return pd.DataFrame(columns=RETAIL_COLUMNS)

    df = pd.concat([df_raw, df_wb], ignore_index=True)

    for col in RETAIL_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[RETAIL_COLUMNS].copy()


def backup_retail_prices(zf: zipfile.ZipFile) -> int:
    """Assemble retail price CSVs from raw JSONL + wayback JSON and write to archive."""
    if not PRICE_SCRAPING_ROOT.exists():
        print("[retail-prices] Root not found, skipping.", file=sys.stderr)
        return 0

    source_dirs = [
        (p.parent.name, p.name, p)
        for p in sorted(PRICE_SCRAPING_ROOT.glob("*/*"))
        if p.is_dir()
    ]
    print(f"[retail-prices] Found {len(source_dirs)} sources")

    count = 0
    warnings: list[str] = []
    for country, source, source_dir in tqdm(
        source_dirs, desc="retail-prices", unit="source"
    ):
        try:
            df = _assemble_source_prices(source_dir, country, source)
            if df.empty:
                continue
            arc_name = f"retail-prices/{country}/{source}/prices.csv"
            buf = StringIO()
            df.to_csv(buf, index=False)
            zf.writestr(arc_name, buf.getvalue())
            count += 1
        except Exception as e:
            warnings.append(f"  WARN [{country}/{source}]: {e}")
    for w in warnings:
        print(w, file=sys.stderr)
    return count


# ── Fuel-prices section ───────────────────────────────────────────────────────


def _build_source_meta(source_key: str) -> dict:
    """Build source metadata dict from FETCHER_REGISTRY, or minimal fallback."""
    config: FetcherConfig | None = FETCHER_REGISTRY.get(source_key)
    if config is None:
        return {"source_key": source_key, "note": "not found in FETCHER_REGISTRY"}
    return {
        "source_key": source_key,
        "source_name": config.source_name,
        "country": config.country,
        "homepage": config.homepage,
        "cadence": config.cadence,
        "full_refresh": config.full_refresh,
        "fallback_date": config.fallback_date.isoformat(),
    }


def backup_fuel_prices(zf: zipfile.ZipFile) -> int:
    """Copy fuel price observations and write source metadata into archive."""
    if not FUEL_PRICES_ROOT.exists():
        print("[fuel-prices] Root not found, skipping.", file=sys.stderr)
        return 0

    obs_files = [
        p
        for p in sorted(FUEL_PRICES_ROOT.glob("*/**/observations.csv"))
        if not any(part.startswith("_") for part in p.parts)
        and not p.parent.name.startswith("gpp_")
    ]
    print(f"[fuel-prices] Found {len(obs_files)} observation files")

    count = 0
    warnings: list[str] = []
    for obs_path in tqdm(obs_files, desc="fuel-prices", unit="source"):
        try:
            rel_parts = obs_path.relative_to(FUEL_PRICES_ROOT).parts
            country = rel_parts[0]
            source = rel_parts[1]
            arc_base = f"fuel-prices/{country}/{source}"

            zf.write(obs_path, arcname=f"{arc_base}/observations.csv")
            meta = _build_source_meta(source)
            zf.writestr(
                f"{arc_base}/source_meta.json",
                json.dumps(meta, indent=2, default=str),
            )
            count += 1
        except Exception as e:
            warnings.append(f"  WARN [{obs_path}]: {e}")
    for w in warnings:
        print(w, file=sys.stderr)
    return count


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """Run the full backup."""
    args = parse_args()
    out_path: Path = args.path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Creating backup → {out_path}")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        n_text = backup_text(zf)
        n_retail = backup_retail_prices(zf)
        n_fuel = backup_fuel_prices(zf)

    size_mb = out_path.stat().st_size / 1_048_576
    print(
        f"\nDone. {out_path.name} ({size_mb:.1f} MB)\n"
        f"  text:          {n_text} files\n"
        f"  retail-prices: {n_retail} sources\n"
        f"  fuel-prices:   {n_fuel} sources"
    )


if __name__ == "__main__":
    main()
