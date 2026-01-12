"""
Report generation orchestration for CPI analysis.

Generates timestamped report outputs and refreshes reports/latest/ for the dashboard.

Usage:
    poetry run python src/cpi/analysis/run_reports.py
    poetry run python src/cpi/analysis/run_reports.py --input path/to/data.csv --outdir path/to/reports
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.functions import (
        load_prices_csv,
        validate_prices,
        build_summary,
        coverage_coicop_l1_overall,
        coverage_coicop_l2_overall,
        coverage_coicop_l3_overall,
        coverage_coicop_l4_overall,
        coverage_coicop_l1_country,
        coverage_coicop_l2_country,
        coverage_coicop_l3_country,
        coverage_coicop_l1_country_source,
        coverage_coicop_l2_country_source,
        coverage_coicop_l3_country_source,
        coverage_time_country_month,
        coverage_time_source_month,
        coverage_time_country_source_month,
        quality_missingness_overall,
        quality_missingness_country,
        quality_missingness_source,
        quality_duplicates,
        quality_wayback_overall,
        quality_wayback_country_source,
        dist_unit_value_country,
        dist_unit_value_country_source,
        dist_unit_value_country_coicop_l3,
        outliers_unit_value_country_coicop_l3,
    )
else:
    from .functions import (
        load_prices_csv,
        validate_prices,
        build_summary,
        coverage_coicop_l1_overall,
        coverage_coicop_l2_overall,
        coverage_coicop_l3_overall,
        coverage_coicop_l4_overall,
        coverage_coicop_l1_country,
        coverage_coicop_l2_country,
        coverage_coicop_l3_country,
        coverage_coicop_l1_country_source,
        coverage_coicop_l2_country_source,
        coverage_coicop_l3_country_source,
        coverage_time_country_month,
        coverage_time_source_month,
        coverage_time_country_source_month,
        quality_missingness_overall,
        quality_missingness_country,
        quality_missingness_source,
        quality_duplicates,
        quality_wayback_overall,
        quality_wayback_country_source,
        dist_unit_value_country,
        dist_unit_value_country_source,
        dist_unit_value_country_coicop_l3,
        outliers_unit_value_country_coicop_l3,
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate CPI analysis reports from supermarket price data."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/cpi/analysis/all_countries_supermarket_prices.csv",
        help="Path to input CSV file (default: data/cpi/analysis/all_countries_supermarket_prices.csv)",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="data/cpi/analysis/reports",
        help="Output directory for reports (default: data/cpi/analysis/reports)",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Skip updating the latest/ directory",
    )
    return parser.parse_args()


def run_reports(input_path: str, outdir: str, update_latest: bool = True):
    """
    Generate all reports and write to timestamped directory.

    Args:
        input_path: Path to input CSV file
        outdir: Base output directory for reports
        update_latest: Whether to update the latest/ symlink/directory
    """
    input_path = Path(input_path)
    outdir = Path(outdir)

    print("=" * 60)
    print("CPI ANALYSIS REPORT GENERATION")
    print("=" * 60)
    print(f"Input: {input_path}")
    print(f"Output directory: {outdir}")
    print()

    # Load and validate data
    print("Loading data...")
    df = load_prices_csv(input_path)
    print(f"  Loaded {len(df):,} rows")

    print("Validating data...")
    df_valid, validation_stats = validate_prices(df)
    print(f"  Valid rows: {validation_stats['valid_rows']:,}")
    print(f"  Invalid unit_value: {validation_stats['invalid_unit_value']:,}")
    print(f"  Invalid date: {validation_stats['invalid_date']:,}")
    print(f"  Invalid COICOP: {validation_stats['invalid_coicop']:,}")
    print()

    # Build summary
    summary = build_summary(df_valid, validation_stats)

    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = outdir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output run directory: {run_dir}")
    print()

    # Define all reports to generate
    reports = {
        "summary.json": None,  # Special handling
        "coverage_coicop_l1_overall.csv": coverage_coicop_l1_overall,
        "coverage_coicop_l2_overall.csv": coverage_coicop_l2_overall,
        "coverage_coicop_l3_overall.csv": coverage_coicop_l3_overall,
        "coverage_coicop_l4_overall.csv": coverage_coicop_l4_overall,
        "coverage_coicop_l1_country.csv": coverage_coicop_l1_country,
        "coverage_coicop_l2_country.csv": coverage_coicop_l2_country,
        "coverage_coicop_l3_country.csv": coverage_coicop_l3_country,
        "coverage_coicop_l1_country_source.csv": coverage_coicop_l1_country_source,
        "coverage_coicop_l2_country_source.csv": coverage_coicop_l2_country_source,
        "coverage_coicop_l3_country_source.csv": coverage_coicop_l3_country_source,
        "coverage_time_country_month.csv": coverage_time_country_month,
        "coverage_time_source_month.csv": coverage_time_source_month,
        "coverage_time_country_source_month.csv": coverage_time_country_source_month,
        "quality_missingness_overall.csv": quality_missingness_overall,
        "quality_missingness_country.csv": quality_missingness_country,
        "quality_missingness_source.csv": quality_missingness_source,
        "quality_duplicates.csv": quality_duplicates,
        "quality_wayback_overall.csv": quality_wayback_overall,
        "quality_wayback_country_source.csv": quality_wayback_country_source,
        "dist_unit_value_country.csv": dist_unit_value_country,
        "dist_unit_value_country_source.csv": dist_unit_value_country_source,
        "dist_unit_value_country_coicop_l3.csv": dist_unit_value_country_coicop_l3,
        "outliers_unit_value_country_coicop_l3.csv": outliers_unit_value_country_coicop_l3,
    }

    # Generate and write reports
    print("Generating reports...")
    for filename, func in reports.items():
        filepath = run_dir / filename

        if filename == "summary.json":
            # Write summary as JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"  ✓ {filename}")
        else:
            # Generate and write CSV
            try:
                result_df = func(df_valid)
                result_df.to_csv(filepath, index=False, encoding="utf-8")
                print(f"  ✓ {filename} ({len(result_df):,} rows)")
            except Exception as e:
                print(f"  ✗ {filename}: {e}")

    print()

    # Update latest/ directory
    if update_latest:
        latest_dir = outdir / "latest"
        print(f"Updating latest/ directory: {latest_dir}")

        # Remove existing latest directory if it exists
        if latest_dir.exists():
            shutil.rmtree(latest_dir)

        # Copy all files from run_dir to latest_dir
        shutil.copytree(run_dir, latest_dir)
        print(f"  ✓ Copied {len(list(run_dir.iterdir()))} files to latest/")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  n_obs: {summary['n_obs']:,}")
    print(f"  n_items: {summary['n_items']:,}")
    print(f"  n_countries: {summary['n_countries']}")
    print(f"  n_sources: {summary['n_sources']}")
    print(f"  date range: {summary['min_date']} to {summary['max_date']}")
    print(f"  n_months: {summary['n_months']}")
    print(f"  n_coicop_3digit: {summary['n_coicop_3digit']}")
    print(f"  n_coicop_4digit: {summary['n_coicop_4digit']}")
    print("=" * 60)
    print()
    print(f"Reports written to: {run_dir}")
    if update_latest:
        print(f"Latest updated at: {latest_dir}")


def main():
    """Main entry point."""
    args = parse_args()
    run_reports(
        input_path=args.input,
        outdir=args.outdir,
        update_latest=not args.no_latest,
    )


if __name__ == "__main__":
    main()
