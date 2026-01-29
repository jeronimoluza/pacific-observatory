"""
Report generation orchestration for CPI analysis.

Generates timestamped report outputs and refreshes reports/latest/ for the dashboard.

Usage:
    poetry run python src/cpi/analysis/run_reports.py
    poetry run python src/cpi/analysis/run_reports.py --input path/to/data.csv --outdir path/to/reports
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.cpi.analysis.core import (
    load_prices,
    compute_log_prices,
    filter_usable,
    filter_by_tier,
    add_coicop_levels,
    create_matched_pairs,
    compute_price_changes,
)
from src.cpi.analysis.indicators import (
    aggregate_inflation,
    compute_price_levels,
    compute_diffusion,
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
        default="data/cpi/analysis/results",
        help="Output directory for reports (default: data/cpi/analysis/reports)",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Skip updating the latest/ directory",
    )
    parser.add_argument(
        "--tiers",
        type=float,
        nargs="+",
        default=None,
        help="Filter by extraction tiers (e.g., --tiers 1 2)",
    )
    parser.add_argument(
        "--countries",
        type=str,
        nargs="+",
        default=None,
        help="Filter by countries (e.g., --countries fiji samoa)",
    )
    return parser.parse_args()


def run_reports(
    input_path: str,
    outdir: str,
    update_latest: bool = True,
    tiers: Optional[List[float]] = None,
    countries: Optional[List[str]] = None,
):
    """
    Generate all reports and write to timestamped directory.

    Args:
        input_path: Path to input CSV file
        outdir: Base output directory for reports
        update_latest: Whether to update the latest/ symlink/directory
        tiers: Optional list of extraction tiers to filter (e.g., [1.0, 2.0])
        countries: Optional list of countries to filter (e.g., ['fiji', 'samoa'])
    """
    print("=" * 70)
    print("CPI ANALYSIS - PHASE 1: CORE MONTHLY INFLATION INDICATORS")
    print("=" * 70)

    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output_dir = Path(outdir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Output directory: {output_dir}")

    # Step 1: Load data
    print(f"\n📊 Loading data from {input_path}...")
    df = load_prices(input_path)
    print(f"✓ Loaded {len(df):,} observations")

    # Step 2: Filter to usable observations
    print("\n🔍 Filtering to usable observations...")
    df = filter_usable(df)
    print(f"✓ Retained {len(df):,} usable observations")

    # Step 3: Apply tier filter if specified
    if tiers is not None:
        print(f"\n🎯 Filtering to tiers: {tiers}")
        df = filter_by_tier(df, tiers)
        print(f"✓ Retained {len(df):,} observations")

    # Step 4: Apply country filter if specified
    if countries is not None:
        print(f"\n🌍 Filtering to countries: {countries}")
        df = df[df["country"].isin(countries)]
        print(f"✓ Retained {len(df):,} observations")

    # Step 5: Add COICOP levels
    print("\n🏷️  Adding COICOP hierarchy levels...")
    df = add_coicop_levels(df)
    print("✓ Added coicop_1, coicop_2, coicop_3, coicop_4 columns")

    # Step 6: Compute log prices
    print("\n📈 Computing log prices...")
    df = compute_log_prices(df)
    print("✓ Added log_unit_value column")

    # Step 7: Create matched pairs
    print("\n🔗 Creating matched pairs for consecutive months...")
    matched = create_matched_pairs(df)
    print(f"✓ Created {len(matched):,} matched pairs")

    # Step 8: Compute price changes
    print("\n📉 Computing price changes...")
    matched = compute_price_changes(matched)
    print("✓ Added delta_p column")

    # Step 9: Generate reports for each COICOP level
    print("\n" + "=" * 70)
    print("GENERATING REPORTS BY COICOP LEVEL")
    print("=" * 70)

    for level in [1, 2, 3, 4]:
        print(f"\n📊 COICOP Level {level}")
        print("-" * 70)

        level_dir = output_dir / f"coicop_lvl_{level}"
        level_dir.mkdir(parents=True, exist_ok=True)

        coicop_col = f"coicop_{level}"
        groupby_cols = ["country", coicop_col, "year_month_t"]

        # 9.1: Matched-model inflation
        print("  • Computing inflation indicators...")
        inflation_df = aggregate_inflation(matched, groupby_cols)
        inflation_path = level_dir / "inflation.csv"
        inflation_df.to_csv(inflation_path, index=False)
        print(f"    ✓ Saved to {inflation_path.relative_to(output_dir)}")

        # 9.2: Price levels
        print("  • Computing price levels...")
        price_groupby = ["country", coicop_col, "year_month"]
        price_levels_df = compute_price_levels(df, price_groupby)
        price_levels_path = level_dir / "price_levels.csv"
        price_levels_df.to_csv(price_levels_path, index=False)
        print(f"    ✓ Saved to {price_levels_path.relative_to(output_dir)}")

        # 9.3: Diffusion indices
        print("  • Computing diffusion indices...")
        diffusion_df = compute_diffusion(matched, groupby_cols)
        diffusion_path = level_dir / "diffusion.csv"
        diffusion_df.to_csv(diffusion_path, index=False)
        print(f"    ✓ Saved to {diffusion_path.relative_to(output_dir)}")

    # Step 10: Update latest symlink/directory
    if update_latest:
        print("\n🔗 Updating latest/ directory...")
        latest_dir = Path(outdir) / "latest"

        # Remove existing latest directory/symlink
        if latest_dir.exists() or latest_dir.is_symlink():
            if latest_dir.is_symlink():
                latest_dir.unlink()
            else:
                import shutil

                shutil.rmtree(latest_dir)

        # Create symlink (Unix/Mac) or copy directory (Windows fallback)
        try:
            latest_dir.symlink_to(timestamp, target_is_directory=True)
            print(f"✓ Created symlink: latest/ → {timestamp}/")
        except (OSError, NotImplementedError):
            import shutil

            shutil.copytree(output_dir, latest_dir)
            print("✓ Copied to latest/ (symlink not supported)")

    print("\n" + "=" * 70)
    print("✅ PHASE 1 REPORTS COMPLETE")
    print("=" * 70)
    print(f"\n📂 Results saved to: {output_dir}")
    print("📊 Generated reports for COICOP levels 1-4")
    print("   • inflation.csv - Matched-model inflation indicators")
    print("   • price_levels.csv - Price level tracking")
    print("   • diffusion.csv - Breadth and diffusion indices")
    print()


def main():
    """Main entry point."""
    args = parse_args()
    run_reports(
        input_path=args.input,
        outdir=args.outdir,
        update_latest=not args.no_latest,
        tiers=args.tiers,
        countries=args.countries,
    )


if __name__ == "__main__":
    main()
