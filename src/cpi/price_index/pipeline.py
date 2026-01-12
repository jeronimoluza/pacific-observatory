"""
CPI Construction Pipeline.

Orchestrates the full CPI construction workflow:
1. Load and validate price data
2. Compute elementary aggregates (Jevons indices)
3. Aggregate to Division 01 using Young Index
4. Export results

Usage:
    python -m src.cpi.analysis.pipeline --help
    python -m src.cpi.analysis.pipeline --country fiji --reference-month 2025-11
"""

import argparse
import sys
from pathlib import Path

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    # Direct execution: add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.data_loader import load_and_prepare, summarize_data
    from src.cpi.analysis.elementary_aggregates import compute_elementary_aggregates
    from src.cpi.analysis.higher_aggregation import (
        compute_higher_aggregation,
    )
    from src.cpi.analysis.output import export_all
else:
    # Module import: use relative imports
    from .data_loader import load_and_prepare, summarize_data
    from .elementary_aggregates import compute_elementary_aggregates
    from .higher_aggregation import compute_higher_aggregation
    from .output import export_all


# Default paths relative to project root
DEFAULT_PRICE_DATA = "data/cpi/analysis/all_countries_supermarket_prices.csv"
DEFAULT_OUTPUT_DIR = "data/cpi/analysis/output"
DEFAULT_REFERENCE_MONTH = "2025-11"


def construct_cpi(
    price_data_path: str | Path,
    country: str,
    reference_month: str = DEFAULT_REFERENCE_MONTH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    include_article_details: bool = False,
) -> dict:
    """
    Construct CPI for a country using the full pipeline.

    Args:
        price_data_path: Path to price data CSV
        country: Country to filter data for
        reference_month: Reference month (base period), format 'YYYY-MM'
        output_dir: Directory for output files
        include_article_details: If True, export article-level data

    Returns:
        Dictionary with results and exported file paths
    """
    print("\n" + "#" * 70)
    print(f"# CPI CONSTRUCTION: {country.upper()}")
    print(f"# Reference Month: {reference_month}")
    print("#" * 70)

    results = {
        "country": country,
        "reference_month": reference_month,
        "stats": {},
    }

    # Step 1: Load and prepare data
    df, data_stats = load_and_prepare(
        price_data_path,
        country=country,
        division_01_only=True,
    )
    results["stats"]["data_stats"] = data_stats

    # Summarize data
    data_summary = summarize_data(df)
    results["data_summary"] = data_summary

    # Check if we have data for reference month
    if reference_month not in df["month"].values:
        available_months = sorted(df["month"].unique())
        raise ValueError(
            f"Reference month {reference_month} not found in data. "
            f"Available months: {available_months}"
        )

    # Step 2: Compute elementary aggregates
    jevons_indices, article_relatives, ea_stats = compute_elementary_aggregates(
        df, reference_month
    )
    results["stats"]["ea_stats"] = ea_stats
    results["jevons_indices"] = jevons_indices
    results["article_relatives"] = article_relatives

    # Step 3: Higher-level aggregation
    young_index, ea_with_weights, contributions, agg_stats = compute_higher_aggregation(
        jevons_indices, reference_month
    )
    results["stats"]["agg_stats"] = agg_stats
    results["young_index"] = young_index
    results["ea_with_weights"] = ea_with_weights
    results["contributions"] = contributions

    # Step 4: Export results
    exported_files = export_all(
        young_index=young_index,
        ea_with_weights=ea_with_weights,
        contributions=contributions,
        article_relatives=article_relatives,
        stats=results["stats"],
        output_dir=output_dir,
        country=country,
        reference_month=reference_month,
        include_article_details=include_article_details,
    )
    results["exported_files"] = exported_files

    print("\n" + "#" * 70)
    print("# CPI CONSTRUCTION COMPLETE")
    print("#" * 70 + "\n")

    return results


def get_project_root() -> Path:
    """Get project root directory."""
    # Navigate up from this file to find project root
    current = Path(__file__).resolve()
    # src/cpi/analysis/pipeline.py -> go up 4 levels
    for _ in range(4):
        current = current.parent
    return current


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Construct CPI from scraped price data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Construct CPI for Fiji with November 2025 as reference
    python -m src.cpi.analysis.pipeline --country fiji --reference-month 2025-11

    # Construct CPI for Australia with custom output directory
    python -m src.cpi.analysis.pipeline --country australia --output-dir ./output

    # Include article-level details in output
    python -m src.cpi.analysis.pipeline --country fiji --include-article-details
        """,
    )

    parser.add_argument(
        "--country",
        type=str,
        required=True,
        help="Country to construct CPI for (e.g., fiji, australia, vanuatu)",
    )

    parser.add_argument(
        "--reference-month",
        type=str,
        default=DEFAULT_REFERENCE_MONTH,
        help=f"Reference month in YYYY-MM format (default: {DEFAULT_REFERENCE_MONTH})",
    )

    parser.add_argument(
        "--price-data",
        type=str,
        default=None,
        help=f"Path to price data CSV (default: {DEFAULT_PRICE_DATA})",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )

    parser.add_argument(
        "--include-article-details",
        action="store_true",
        help="Include article-level price relatives in output (can be large)",
    )

    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = get_project_root()

    price_data_path = (
        Path(args.price_data) if args.price_data else project_root / DEFAULT_PRICE_DATA
    )

    output_dir = (
        Path(args.output_dir) if args.output_dir else project_root / DEFAULT_OUTPUT_DIR
    )

    # Run pipeline
    try:
        results = construct_cpi(
            price_data_path=price_data_path,
            country=args.country,
            reference_month=args.reference_month,
            output_dir=output_dir,
            include_article_details=args.include_article_details,
        )

        print(f"\n✓ CPI construction complete for {args.country}")
        print(f"  Output files saved to: {output_dir}")

        return results

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("  Make sure the price data file exists.")
        return None

    except ValueError as e:
        print(f"\n✗ Error: {e}")
        return None


if __name__ == "__main__":
    main()
