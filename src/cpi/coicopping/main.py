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
    from .utils import get_project_root
    from .classification import reclassify_missing_classifications
    from .classify import run_classify
    from .load import run_load
    from .merge import run_merge
    from .quantities import run_quantities
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from utils import get_project_root
    from classification import reclassify_missing_classifications
    from classify import run_classify
    from load import run_load
    from merge import run_merge
    from quantities import run_quantities


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

    logger = logging.getLogger(__name__)

    print("=" * 80)
    print("COICOP CLASSIFICATION WORKFLOW")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("STEP 1: Load and prepare data")
    print("=" * 80)
    logger.info("Running load stage...")
    run_load(project_root)

    print("\n" + "=" * 80)
    print("STEP 2: Extract quantities (Standardized Unit Price System)")
    print("=" * 80)
    logger.info("Running quantities stage...")
    run_quantities(project_root)

    if not skip_classification:
        print("\n" + "=" * 80)
        print("STEP 3: Classify with COICOP using Gemini AI")
        print("=" * 80)
        logger.info("Running classify stage...")
        run_classify(project_root)
    else:
        print("\n" + "=" * 80)
        print("STEP 3: SKIPPED - Using existing classifications")
        print("=" * 80)

    print("\n" + "=" * 80)
    print("STEP 4: Merge & Finalize")
    print("=" * 80)
    logger.info("Running merge stage...")
    df_final = run_merge(project_root)

    output_path = (
        project_root
        / "data"
        / "cpi"
        / "analysis"
        / "all_countries_supermarket_prices.csv"
    )

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

    print("\n" + "-" * 40)
    print("STANDARDIZED UNIT PRICE METRICS")
    print("-" * 40)
    if "usability_status" in df_final.columns:
        print("\nUsability Status Distribution:")
        status_counts = df_final["usability_status"].value_counts()
        for status, count in status_counts.items():
            pct = count / len(df_final) * 100
            print(f"  {status}: {count} ({pct:.1f}%)")

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

    if "extraction_tier" in df_final.columns:
        print("\nExtraction Tier Statistics:")
        tier_counts = df_final["extraction_tier"].value_counts().sort_index()
        for tier, count in tier_counts.items():
            pct = count / len(df_final) * 100
            tier_desc = {1: "Weight/Volume", 2: "Count", 3: "Per-item"}.get(
                tier, "Excluded"
            )
            print(f"  Tier {tier} ({tier_desc}): {count} ({pct:.1f}%)")
        excluded = df_final["extraction_tier"].isna().sum()
        if excluded > 0:
            print(
                f"  Excluded (no tier): {excluded} ({excluded / len(df_final) * 100:.1f}%)"
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

  # Reclassify missing COICOP codes (ONLY runs reclassification)
  poetry run python src/cpi/coicopping/main.py --reclassify-missing

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
        "--reclassify-missing",
        action="store_true",
        help="Reclassify missing COICOP codes in gemini_classification.csv (ONLY runs reclassification)",
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
        if args.reclassify_missing:
            # Only run reclassification
            reclassify_missing_classifications()
        else:
            # Run complete workflow
            df_final = run_complete_workflow(
                skip_classification=args.skip_classification,
            )
    except Exception as e:
        logging.error(f"Workflow failed: {e}", exc_info=True)
        sys.exit(1)
