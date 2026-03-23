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
import sys
import zipfile
from datetime import date
from pathlib import Path

# ── Repo layout ───────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_ROOT = REPO_ROOT / "data" / "text"
PRICE_SCRAPING_ROOT = REPO_ROOT / "data" / "cpi" / "price_scraping"
FUEL_PRICES_ROOT = REPO_ROOT / "data" / "cpi" / "fuel_prices"

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
    for csv_path in csv_files:
        try:
            rel = csv_path.relative_to(TEXT_ROOT)
            zf.write(csv_path, arcname=f"text/{rel}")
            count += 1
        except Exception as e:
            warnings.append(f"  WARN [{csv_path.name}]: {e}")
    for w in warnings:
        print(w, file=sys.stderr)
    return count


def backup_retail_prices(zf: zipfile.ZipFile) -> int:
    """Copy the assembled supermarket prices CSV into the archive."""
    retail_csv = PRICE_SCRAPING_ROOT / "all_countries_supermarket_prices.csv"
    if not retail_csv.exists():
        print("[retail-prices] CSV not found, skipping.", file=sys.stderr)
        return 0

    try:
        zf.write(
            retail_csv, arcname="retail-prices/all_countries_supermarket_prices.csv"
        )
        print("[retail-prices] Added all_countries_supermarket_prices.csv")
        return 1
    except Exception as e:
        print(f"  WARN [retail-prices]: {e}", file=sys.stderr)
        return 0


# ── Fuel-prices section ───────────────────────────────────────────────────────
def backup_fuel_prices(zf: zipfile.ZipFile) -> int:
    """Copy enriched fuel prices CSV into the archive."""
    fuel_csv = (
        REPO_ROOT
        / "data"
        / "cpi"
        / "fuel_prices_staged"
        / "enrich"
        / "retail_series_enriched.csv"
    )
    if not fuel_csv.exists():
        print("[fuel-prices] CSV not found, skipping.", file=sys.stderr)
        return 0

    try:
        zf.write(fuel_csv, arcname="fuel-prices/retail_series_enriched.csv")
        print("[fuel-prices] Added retail_series_enriched.csv")
        return 1
    except Exception as e:
        print(f"  WARN [fuel-prices]: {e}", file=sys.stderr)
        return 0


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
