"""
Main orchestration script for COICOP classification workflow.

This script runs the complete pipeline:
1. Load price scraping data (scrapy + wayback)
2. Clean and prepare data
3. Extract quantities (amount, units, unit_value)
4. Classify products with COICOP using Gemini AI
5. Merge and finalize output

Output: data/cpi/analysis/all_countries_supermarket_prices.csv
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Handle both relative and direct execution
try:
    from .prestep import prepare_coicop_matching_data
    from .extract_quantities import extract_quantities, merge_quantities_with_gemini
    from .coicop_matching import run_coicop_matching
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from prestep import prepare_coicop_matching_data
    from extract_quantities import extract_quantities, merge_quantities_with_gemini
    from coicop_matching import run_coicop_matching


def setup_logging(level: str = "INFO") -> None:
    """
    Setup logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_project_root(current_file: Path = None) -> Path:
    """Get the project root directory."""
    if current_file is None:
        current_file = Path(__file__)
    return current_file.parent.parent.parent.parent


def run_complete_workflow(
    project_root: Optional[Path] = None,
    skip_classification: bool = False,
) -> pd.DataFrame:
    """
    Run the complete COICOP classification workflow.

    Workflow steps:
    1. Load price scraping data (scrapy JSONL + wayback JSON)
    2. Clean and prepare data (remove quantities, create product_w_cat)
    3. Extract quantities (amount, units, unit_value)
    4. Classify with COICOP using Gemini AI (if not skipped)
    5. Merge quantities with classifications
    6. Save final output to CSV

    Args:
        project_root: Optional project root path. If None, infers from this file's location.
        skip_classification: If True, skip COICOP classification step (use existing gemini_classification.csv)

    Returns:
        Final DataFrame with all data
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "cpi" / "coicopping"
    output_dir = project_root / "data" / "cpi" / "analysis"
    gemini_classification_path = data_dir / "gemini_classification.csv"
    output_path = output_dir / "all_countries_supermarket_prices.csv"

    logger = logging.getLogger(__name__)

    print("=" * 80)
    print("COICOP CLASSIFICATION WORKFLOW")
    print("=" * 80)

    # STEP 1: Load and prepare data
    print("\n" + "=" * 80)
    print("STEP 1: Load and prepare data")
    print("=" * 80)
    logger.info("Loading price scraping data (scrapy + wayback) and preparing...")
    df_prepared = prepare_coicop_matching_data(project_root)
    print(f"✓ Loaded and prepared {len(df_prepared)} records")
    print(f"  - Scrapy records: {len(df_prepared[df_prepared['wayback'] == 0])}")
    print(f"  - Wayback records: {len(df_prepared[df_prepared['wayback'] == 1])}")
    print(f"  - Columns: {df_prepared.columns.tolist()}")

    # STEP 2: Extract quantities (with standardized unit price system)
    print("\n" + "=" * 80)
    print("STEP 2: Extract quantities (Standardized Unit Price System)")
    print("=" * 80)
    logger.info("Extracting quantities with multi-candidate extraction...")
    # Pass prepared data to avoid re-preparing
    df_quantities = extract_quantities(
        df_prepared=df_prepared, project_root=project_root
    )
    print(f"✓ Extracted quantities for {len(df_quantities)} records")
    print(f"  - Records with amount: {df_quantities['amount'].notna().sum()}")
    print(f"  - Records with units: {df_quantities['units'].notna().sum()}")
    print(f"  - Records with unit_value: {df_quantities['unit_value'].notna().sum()}")

    # Print usability status distribution
    print("\n  Usability status distribution:")
    status_counts = df_quantities["usability_status"].value_counts()
    for status, count in status_counts.items():
        pct = count / len(df_quantities) * 100
        print(f"    - {status}: {count} ({pct:.1f}%)")

    # Calculate resolved rate
    resolved_statuses = [
        "resolved_mass",
        "resolved_volume",
        "resolved_length",
        "resolved_count_food",
    ]
    resolved_count = df_quantities[
        df_quantities["usability_status"].isin(resolved_statuses)
    ].shape[0]
    resolved_pct = resolved_count / len(df_quantities) * 100
    print(f"\n  Total resolved: {resolved_count} ({resolved_pct:.1f}%)")

    # Print promotion detection summary
    promo_count = df_quantities["has_promotion"].sum()
    print(f"  Products flagged as promotional: {promo_count}")

    # Print confidence score distribution
    print("\n  Confidence score statistics:")
    print(f"    - Mean: {df_quantities['confidence_score'].mean():.2f}")
    print(f"    - Median: {df_quantities['confidence_score'].median():.2f}")
    print(f"    - Min: {df_quantities['confidence_score'].min():.2f}")
    print(f"    - Max: {df_quantities['confidence_score'].max():.2f}")

    # STEP 3: Classify with COICOP (if not skipped)
    if not skip_classification:
        print("\n" + "=" * 80)
        print("STEP 3: Classify with COICOP using Gemini AI")
        print("=" * 80)
        logger.info("Running COICOP classification...")
        # Pass prepared data to avoid re-preparing
        run_coicop_matching(df_prepared=df_prepared, project_root=project_root)
        print("✓ Classification complete")
    else:
        print("\n" + "=" * 80)
        print("STEP 3: SKIPPED - Using existing classifications")
        print("=" * 80)
        if gemini_classification_path.exists():
            print(f"✓ Using existing file: {gemini_classification_path}")
        else:
            print(f"⚠ Warning: {gemini_classification_path} not found")
            print("  Continuing without classifications...")

    # STEP 4: Merge & Finalize
    print("\n" + "=" * 80)
    print("STEP 4: Merge & Finalize")
    print("=" * 80)
    logger.info("Merging quantities with COICOP classifications...")

    # Use the merge_quantities_with_gemini function as specified in README
    df_final = merge_quantities_with_gemini(df_quantities, gemini_classification_path)

    # Select final columns (including new standardized unit price columns)
    final_columns = [
        "url_hash",
        "product_name",
        "product_w_cat",
        "price",
        "currency",
        "amount",
        "units",
        "unit_value",
        "usability_status",
        "confidence_score",
        "standard_unit",
        "n_candidates",
        "has_promotion",
        "rejection_reason",
        "coicop_code",
        "coicop_title",
        "source",
        "country",
        "product_url",
        "date",
        "product_id",
        "wayback",
    ]

    # Only include columns that exist
    available_columns = [col for col in final_columns if col in df_final.columns]
    df_final = df_final[available_columns]

    # Save to CSV
    output_dir.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output_path, index=False, encoding="utf-8")
    print(f"✓ Saved {len(df_final)} records to {output_path}")

    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total records: {len(df_final)}")
    print(f"Unique products (url_hash): {df_final['url_hash'].nunique()}")
    print(f"Countries: {df_final['country'].nunique()}")
    print(f"Sources: {df_final['source'].nunique()}")
    if "coicop_code" in df_final.columns:
        print(f"Classified products: {df_final['coicop_code'].notna().sum()}")
        print(f"Unclassified products: {df_final['coicop_code'].isna().sum()}")
        print(f"Unique COICOP codes: {df_final['coicop_code'].nunique()}")
    print(f"Records with amount: {df_final['amount'].notna().sum()}")
    print(f"Records with unit_value: {df_final['unit_value'].notna().sum()}")
    print(f"Date range: {df_final['date'].min()} to {df_final['date'].max()}")

    # Print standardized unit price system metrics
    print("\n" + "-" * 40)
    print("STANDARDIZED UNIT PRICE METRICS")
    print("-" * 40)
    if "usability_status" in df_final.columns:
        # Usability status distribution
        print("\nUsability Status Distribution:")
        status_counts = df_final["usability_status"].value_counts()
        for status, count in status_counts.items():
            pct = count / len(df_final) * 100
            print(f"  {status}: {count} ({pct:.1f}%)")

        # Calculate resolved rate (PRD success metric)
        resolved_statuses = [
            "resolved_mass",
            "resolved_volume",
            "resolved_length",
            "resolved_count_food",
        ]
        resolved_count = df_final[
            df_final["usability_status"].isin(resolved_statuses)
        ].shape[0]
        resolved_pct = resolved_count / len(df_final) * 100
        print(f"\n  TOTAL RESOLVED: {resolved_count} ({resolved_pct:.1f}%)")

        # Food products resolved rate (target: >= 30%)
        if "coicop_code" in df_final.columns:
            food_products = df_final[
                df_final["coicop_code"].str.startswith("01", na=False)
            ]
            if len(food_products) > 0:
                food_resolved = food_products[
                    food_products["usability_status"].isin(resolved_statuses)
                ].shape[0]
                food_resolved_pct = food_resolved / len(food_products) * 100
                print(
                    f"  Food products resolved: {food_resolved}/{len(food_products)} ({food_resolved_pct:.1f}%)"
                )
                if food_resolved_pct >= 30:
                    print("  ✓ PRD Target Met: >= 30% food products resolved")
                else:
                    print(f"  ⚠ PRD Target Not Met: {food_resolved_pct:.1f}% < 30%")

    if "has_promotion" in df_final.columns:
        promo_count = df_final["has_promotion"].sum()
        print(f"\nPromotional products detected: {promo_count}")

    if "confidence_score" in df_final.columns:
        print("\nConfidence Score Statistics:")
        print(f"  Mean: {df_final['confidence_score'].mean():.3f}")
        print(f"  Median: {df_final['confidence_score'].median():.3f}")
        print(
            f"  High confidence (>= 0.75): {(df_final['confidence_score'] >= 0.75).sum()}"
        )
        print(
            f"  Medium confidence (0.50-0.74): {((df_final['confidence_score'] >= 0.50) & (df_final['confidence_score'] < 0.75)).sum()}"
        )
        print(
            f"  Low confidence (< 0.50): {(df_final['confidence_score'] < 0.50).sum()}"
        )

    print("\n" + "=" * 80)
    print("✓ WORKFLOW COMPLETE!")
    print("=" * 80)
    print(f"\nOutput file: {output_path}")
    print("\nNext steps:")
    print("  1. Review the output file for data quality")
    print("  2. Check unclassified products and manually classify if needed")
    print("  3. Use the data for CPI analysis and price tracking")
    print("\n")

    return df_final


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run COICOP classification workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete workflow (including classification)
  poetry run python src/cpi/coicopping/main.py

  # Skip classification (use existing gemini_classification.csv)
  poetry run python src/cpi/coicopping/main.py --skip-classification

  # Run with debug logging
  poetry run python src/cpi/coicopping/main.py --log-level DEBUG
        """,
    )

    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Skip COICOP classification step (use existing gemini_classification.csv)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Run workflow
    try:
        df_final = run_complete_workflow(
            skip_classification=args.skip_classification,
        )
    except Exception as e:
        logging.error(f"Workflow failed: {e}", exc_info=True)
        sys.exit(1)
