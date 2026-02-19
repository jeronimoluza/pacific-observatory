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
    convert_timezone,
    build_fx_rate_table,
    convert_to_usd,
)
from src.cpi.analysis.indicators import (
    aggregate_inflation,
    compute_price_levels,
    compute_diffusion,
)
from src.cpi.analysis.microstructure import (
    compute_change_frequency,
    compute_price_spells,
    aggregate_spells,
    classify_sticky_flexible,
)
from src.cpi.analysis.cross_country import (
    compute_price_levels_usd,
    compute_ppp_ratios,
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
    parser.add_argument(
        "--skip-ppp",
        action="store_true",
        help="Skip PPP cross-country comparisons (avoids FX API calls)",
    )
    parser.add_argument(
        "--fx-cache",
        type=str,
        default="data/cpi/analysis/fx_cache.csv",
        help="Path to FX rate cache file (default: data/cpi/analysis/fx_cache.csv)",
    )
    return parser.parse_args()


def run_reports(
    input_path: str,
    outdir: str,
    update_latest: bool = True,
    tiers: Optional[List[float]] = None,
    countries: Optional[List[str]] = None,
    skip_ppp: bool = False,
    fx_cache: str = "data/cpi/analysis/fx_cache.csv",
):
    """
    Generate all reports and write to timestamped directory.

    Args:
        input_path: Path to input CSV file
        outdir: Base output directory for reports
        update_latest: Whether to update the latest/ symlink/directory
        tiers: Optional list of extraction tiers to filter (e.g., [1.0, 2.0])
        countries: Optional list of countries to filter (e.g., ['fiji', 'samoa'])
        skip_ppp: Whether to skip PPP cross-country comparisons
        fx_cache: Path to FX rate cache file
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
    print("\n🔗 Creating matched pairs across available months...")
    matched = create_matched_pairs(df)
    print(f"✓ Created {len(matched):,} matched pairs")

    # Step 8: Compute price changes
    print("\n📉 Computing price changes...")
    matched = compute_price_changes(matched)
    print("✓ Added delta_p column")

    # Step 8.5: Compute price spells (uses raw df, not matched pairs)
    print("\n🔒 Computing price spells...")
    spells = compute_price_spells(df)
    print(
        f"✓ Computed {len(spells):,} price spells across {spells['url_hash'].nunique():,} products"
    )

    # Step 8.6: PPP preparation (timezone conversion + FX rates)
    if not skip_ppp:
        print("\n💱 Preparing cross-country PPP comparisons...")

        print("  • Converting timestamps to local timezones...")
        df = convert_timezone(df)
        print("  ✓ Added date_local and date_local_date columns")

        print("  • Building FX rate table...")
        fx_rates = build_fx_rate_table(df, cache_path=fx_cache)
        print(f"  ✓ FX rate table: {len(fx_rates):,} rate observations")

        print("  • Converting prices to USD...")
        df = convert_to_usd(df, fx_rates)
        n_converted = df["unit_value_usd"].notna().sum()
        print(f"  ✓ Converted {n_converted:,} / {len(df):,} prices to USD")

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

        # 9.4: Change frequency
        print("  • Computing change frequency...")
        freq_df = compute_change_frequency(matched, groupby_cols)
        freq_path = level_dir / "change_frequency.csv"
        freq_df.to_csv(freq_path, index=False)
        print(f"    ✓ Saved to {freq_path.relative_to(output_dir)}")

        # 9.5: Spell aggregation
        print("  • Aggregating price spells...")
        spell_groupby = ["country", coicop_col]
        spells_agg = aggregate_spells(spells, spell_groupby)
        spells_path = level_dir / "spells.csv"
        spells_agg.to_csv(spells_path, index=False)
        print(f"    ✓ Saved to {spells_path.relative_to(output_dir)}")

        # 9.6: Sticky/flexible classification
        print("  • Classifying sticky/flexible products...")
        sticky_df = classify_sticky_flexible(spells, spell_groupby)
        sticky_path = level_dir / "sticky_flexible.csv"
        sticky_df.to_csv(sticky_path, index=False)
        print(f"    ✓ Saved to {sticky_path.relative_to(output_dir)}")

        # 9.7: PPP comparisons (if enabled)
        if not skip_ppp:
            print("  • Computing PPP price levels (USD)...")
            ppp_groupby = ["country", coicop_col, "year_month"]
            ppp_levels = compute_price_levels_usd(df, ppp_groupby)
            ppp_levels_path = level_dir / "ppp_price_levels.csv"
            ppp_levels.to_csv(ppp_levels_path, index=False)
            print(f"    ✓ Saved to {ppp_levels_path.relative_to(output_dir)}")

            print("  • Computing PPP ratios...")
            ppp_ratios = compute_ppp_ratios(ppp_levels, ppp_groupby)
            ppp_ratios_path = level_dir / "ppp_ratios.csv"
            ppp_ratios.to_csv(ppp_ratios_path, index=False)
            print(f"    ✓ Saved to {ppp_ratios_path.relative_to(output_dir)}")

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
    print("✅ REPORTS COMPLETE")
    print("=" * 70)
    print(f"\n📂 Results saved to: {output_dir}")
    print("📊 Generated reports for COICOP levels 1-4")
    print("   • inflation.csv - Matched-model inflation indicators")
    print("   • price_levels.csv - Price level tracking")
    print("   • diffusion.csv - Breadth and diffusion indices")
    print("   • change_frequency.csv - Price change frequency")
    print("   • spells.csv - Price spell statistics")
    print("   • sticky_flexible.csv - Sticky/flexible product classification")
    if not skip_ppp:
        print(
            "   • ppp_price_levels.csv - USD price levels for cross-country comparison"
        )
        print("   • ppp_ratios.csv - PPP ratios relative to cross-country mean")
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
        skip_ppp=args.skip_ppp,
        fx_cache=args.fx_cache,
    )


if __name__ == "__main__":
    main()
