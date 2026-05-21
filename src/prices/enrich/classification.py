"""
Gemini 2.0 Flash-based COICOP classification workflow.

This module orchestrates the complete workflow:
1. Download COICOP Excel and save processed CSVs
2. Create products_input.csv from price scraping data
3. Classify products using Gemini 2.0 Flash in batches of 2000
4. Generate final gemini_classification.csv with code and title mappings
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# Handle both relative and direct execution
try:
    from .utils import get_project_root
    from .gemini_client import (
        setup_google_api_key,
        format_gemini_prompt,
        parse_gemini_response,
    )
    from .coicop_categories import (
        download_coicop_excel,
        load_and_process_coicop,
    )
    from .data_preparation import prepare_coicop_matching_data
    from .quantity.extraction import extract_and_merge_quantities
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from utils import get_project_root
    from gemini_client import (
        setup_google_api_key,
        format_gemini_prompt,
        parse_gemini_response,
    )
    from coicop_categories import (
        download_coicop_excel,
        load_and_process_coicop,
    )
    from data_preparation import prepare_coicop_matching_data
    from quantity.extraction import extract_and_merge_quantities


def download_and_save_coicop_data(
    project_root: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Download COICOP Excel file and save processed CSVs.

    Saves:
    - data/prices/_enrich/coicop_categories.csv
    - data/prices/_enrich/coicop_categories_no_services.csv

    Args:
        project_root: Optional project root path

    Returns:
        Tuple of (full_df, no_services_df)
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"

    print("\n" + "=" * 70)
    print("STEP 1: Download and process COICOP categories")
    print("=" * 70)

    # Download Excel if needed
    excel_path = download_coicop_excel(data_dir)

    # Load and process COICOP data
    print("\nProcessing COICOP data...")
    df = load_and_process_coicop(excel_path, digit_level=4)

    print(f"✓ Loaded {len(df)} COICOP categories")

    # Save full categories (only code, title, keywords columns)
    csv_path = data_dir / "coicop_categories.csv"
    df[["coicop_code", "coicop_title", "keywords"]].to_csv(csv_path, index=False)
    print(f"✓ Saved to {str(csv_path)}")

    # Save categories without services (only coicop_code, coicop_title, keywords columns)
    df_no_services = df[~df["coicop_code"].str.endswith(" (S)")].copy()
    csv_no_services_path = data_dir / "coicop_categories_no_services.csv"
    df_no_services[["coicop_code", "coicop_title", "keywords"]].to_csv(
        csv_no_services_path, index=False
    )
    print(
        f"✓ Saved {len(df_no_services)} categories (without services) to {str(csv_no_services_path)}"
    )

    return df, df_no_services


def create_products_input_csv(
    df_prepared: Optional[pd.DataFrame] = None,
    project_root: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Create products_input.csv from prepared product data.

    Extracts url_hash and product_w_cat columns and saves to:
    data/prices/_enrich/products_input.csv

    Args:
        df_prepared: Optional pre-prepared DataFrame from prepare_coicop_matching_data().
                    If None, will call prepare_coicop_matching_data() internally.
        project_root: Optional project root path

    Returns:
        DataFrame with url_hash and product_w_cat columns
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("Creating products_input.csv")
    print("=" * 70)

    # Use provided DataFrame or prepare data
    if df_prepared is None:
        print("\nPreparing product data...")
        df_products = prepare_coicop_matching_data(project_root)
    else:
        print("\nUsing pre-prepared product data...")
        df_products = df_prepared

    print(f"✓ Prepared {len(df_products)} products")

    # Sort oldest-first so dedup keeps the earliest observation per url_hash /
    # product_w_cat, and Gemini batches process the oldest products first.
    if "scraped_at_utc" in df_products.columns:
        df_products = df_products.sort_values(
            "scraped_at_utc", ascending=True, na_position="last", kind="stable"
        )
        print("✓ Sorted by scraped_at_utc ascending (oldest first)")

    # Select required columns
    required_cols = ["url_hash", "product_w_cat"]
    missing_cols = [col for col in required_cols if col not in df_products.columns]

    if missing_cols:
        print(f"Available columns: {df_products.columns.tolist()}")
        raise KeyError(f"Missing columns in prepared data: {missing_cols}")

    df_input = df_products[required_cols].copy()

    # Remove duplicates by url_hash (keep first occurrence)
    # This ensures each unique url_hash gets classified
    df_input = df_input.drop_duplicates(subset=["url_hash"], keep="first")
    print(f"✓ After deduplication: {len(df_input)} unique url_hash entries")

    # Remove duplicates by product_w_cat (keep first occurrence)
    # This ensures each unique product name gets classified,
    # avoiding unnecessary Gemini calls
    df_input = df_input.drop_duplicates(subset=["product_w_cat"], keep="first")
    print(f"✓ After deduplication: {len(df_input)} unique product_w_cat entries")

    # Save to CSV
    csv_path = data_dir / "products_input.csv"
    df_input.to_csv(csv_path, index=False)
    print(f"✓ Saved to {csv_path}")

    return df_input


def classify_products_with_gemini(
    products_input_df: pd.DataFrame,
    coicop_no_services_df: pd.DataFrame,
    coicop_categories_df: pd.DataFrame,
    existing_classifications: Optional[pd.DataFrame] = None,
    project_root: Optional[Path] = None,
    batch_size: int = 2000,
) -> pd.DataFrame:
    """
    Classify products using Gemini 3.0 Flash in batches.

    After each batch is classified, it is immediately appended to gemini_classification.csv.
    This allows stopping the process at any point without losing classified batches.

    Args:
        products_input_df: DataFrame with url_hash and product_w_cat
        coicop_no_services_df: COICOP categories (without services)
        coicop_categories_df: Full COICOP categories with titles
        existing_classifications: Optional existing classifications DataFrame
        project_root: Optional project root path
        batch_size: Number of products per batch (default 600)

    Returns:
        DataFrame with url_hash, product_w_cat, code, title
    """
    try:
        import google.generativeai as genai
    except ImportError:
        print("\nERROR: google-generativeai library not installed")
        print("Install it with: pip install google-generativeai")
        raise

    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"
    gemini_classification_path = data_dir / "gemini_classification.csv"

    print("\n" + "=" * 70)
    print("STEP 3: Classify products with Gemini AI")
    print("=" * 70)

    # Setup API
    api_key = setup_google_api_key()
    genai.configure(api_key=api_key)

    # Prepare data
    unique_products = (
        products_input_df[["product_w_cat"]].drop_duplicates().reset_index(drop=True)
    )
    total_products = len(unique_products)
    num_batches = (total_products + batch_size - 1) // batch_size

    print(
        f"\nClassifying {total_products} products in {num_batches} batches (batch size: {batch_size})"
    )

    all_results = []

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_products)
        batch_products = unique_products.iloc[start_idx:end_idx][
            "product_w_cat"
        ].tolist()

        print(
            f"\nBatch {batch_num + 1}/{num_batches}: Processing {len(batch_products)} products..."
        )

        # Format prompt
        prompt = format_gemini_prompt(batch_products, coicop_no_services_df)

        # Call Gemini API
        try:
            model = genai.GenerativeModel("gemini-3.1-flash-lite")
            response = model.generate_content(prompt)
            response_text = response.text

            # Parse CSV response
            batch_results = parse_gemini_response(response_text)

            # Debug: Show response details if batch is empty
            if len(batch_results) == 0:
                print(f"⚠ Batch {batch_num + 1}: No valid results parsed.")
                print(f"  Response preview (first 300 chars):\n{response_text[:300]}")
                # Check if header is present
                first_line = response_text.split("\n")[0] if response_text else ""
                print(f"  First line: {first_line}")
            else:
                print(
                    f"✓ Batch {batch_num + 1}: Classified {len(batch_results)} products"
                )

                # Immediately process and append this batch to CSV
                batch_df = pd.DataFrame(batch_results)

                # Get the products from this batch to merge with url_hash
                batch_products_df = products_input_df[
                    products_input_df["product_w_cat"].isin(batch_df["product_w_cat"])
                ].copy()

                # Merge batch results with url_hash
                batch_merged = batch_products_df.merge(
                    batch_df, on="product_w_cat", how="left"
                )

                # Merge with COICOP categories to get titles
                batch_merged = batch_merged.merge(
                    coicop_categories_df[["coicop_code", "coicop_title"]],
                    on="coicop_code",
                    how="left",
                )

                # Select final columns (including confidence)
                batch_final = batch_merged[
                    [
                        "url_hash",
                        "product_w_cat",
                        "coicop_code",
                        "coicop_title",
                        "confidence",
                    ]
                ].copy()

                # Remove duplicates
                batch_final = batch_final.drop_duplicates(
                    subset=["url_hash", "product_w_cat"], keep="first"
                )

                # Append to CSV file immediately
                if gemini_classification_path.exists():
                    # Append to existing file
                    batch_final.to_csv(
                        gemini_classification_path,
                        mode="a",
                        header=False,
                        index=False,
                    )
                    print(
                        f"  → Appended {len(batch_final)} records to {gemini_classification_path.name}"
                    )
                else:
                    # Create new file with header
                    batch_final.to_csv(gemini_classification_path, index=False)
                    print(
                        f"  → Created {gemini_classification_path.name} with {len(batch_final)} records"
                    )

                # Also keep in memory for final return
                all_results.extend(batch_results)

        except Exception as e:
            error_msg = str(e).lower()
            # Check for quota exceeded errors
            if (
                "quota" in error_msg
                or "resource_exhausted" in error_msg
                or "429" in error_msg
            ):
                print(f"\n✗ API quota exceeded at batch {batch_num + 1}/{num_batches}")
                print(f"  Error: {e}")
                print(
                    "\n⚠ Stopping remaining batches to preserve existing classifications"
                )
                print(
                    f"  Successfully classified {len(all_results)} products before quota limit"
                )
                # Break out of the loop to stop processing remaining batches
                break
            else:
                print(f"✗ Error processing batch {batch_num + 1}: {e}")
                # Continue with next batch for other errors
                continue

    # Combine results
    if not all_results:
        print("\n⚠ Warning: No products were successfully classified")
        print("  This may be due to API quota limits or other errors")
        print("  Returning empty DataFrame")
        return pd.DataFrame(columns=["product_w_cat", "coicop_code", "confidence"])

    results_df = pd.DataFrame(all_results)
    print(f"\n✓ Total classified: {len(results_df)} products")
    print(f"✓ All batches have been saved to {gemini_classification_path}")

    return results_df


def generate_final_output(
    products_input_df: pd.DataFrame,
    classification_results_df: pd.DataFrame,
    coicop_categories_df: pd.DataFrame,
    project_root: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Generate final gemini_classification.csv with url_hash, product_w_cat, code, title.

    Args:
        products_input_df: Original products with url_hash and product_w_cat
        classification_results_df: Classification results with product_w_cat and code
        coicop_categories_df: COICOP categories with code and title
        project_root: Optional project root path

    Returns:
        Final DataFrame
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"

    print("\n" + "=" * 70)
    print("STEP 4: Generate final output")
    print("=" * 70)

    # Merge products with classifications
    merged = products_input_df.merge(
        classification_results_df, on="product_w_cat", how="left"
    )

    # Merge with COICOP categories to get titles
    merged = merged.merge(
        coicop_categories_df[["coicop_code", "coicop_title"]],
        on="coicop_code",
        how="left",
    )

    # Select final columns and rename to match README specification
    final_df = merged[
        ["url_hash", "product_w_cat", "coicop_code", "coicop_title", "confidence"]
    ].copy()
    # final_df = final_df.rename(columns={"coicop_code": "code", "coicop_title": "title"})

    # Remove duplicates (keep first)
    final_df = final_df.drop_duplicates(
        subset=["url_hash", "product_w_cat"], keep="first"
    )

    print(f"✓ Generated final output with {len(final_df)} records")

    # Save to CSV
    output_path = data_dir / "gemini_classification.csv"
    final_df.to_csv(output_path, index=False)
    print(f"✓ Saved to {output_path}")

    # Print summary
    classified = final_df[final_df["coicop_code"].notna()].shape[0]
    unclassified = final_df[final_df["coicop_code"].isna()].shape[0]

    print("\nSummary:")
    print(f"  - Total records: {len(final_df)}")
    print(f"  - Classified: {classified}")
    print(f"  - Unclassified: {unclassified}")

    return final_df


def run_coicop_matching(
    df_prepared: Optional[pd.DataFrame] = None,
    project_root: Optional[Path] = None,
) -> None:
    """
    Main orchestration function for the complete COICOP matching workflow.

    Implements incremental classification:
    1. Download COICOP Excel and save CSVs
    2. Load existing classifications from gemini_classification.csv (if present)
    3. Create products_input.csv
    4. Identify new/unclassified products (url_hash not in gemini_classification.csv)
    5. Batch classify new products with Gemini (600 products per batch)
    6. Append new classifications to gemini_classification.csv
    7. Merge all classifications back to original data

    Args:
        df_prepared: Optional pre-prepared DataFrame from prepare_coicop_matching_data().
                    If None, will call prepare_coicop_matching_data() internally.
        project_root: Optional project root path
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"
    gemini_classification_path = data_dir / "gemini_classification.csv"

    try:
        # Step 1: Download and process COICOP data
        df_coicop, df_coicop_no_services = download_and_save_coicop_data(project_root)

        # Step 2: Create products input (all products from current data)
        df_products_input = create_products_input_csv(df_prepared, project_root)

        # Step 3: Load existing classifications (if file exists)
        existing_classifications = None
        if gemini_classification_path.exists():
            print("\n" + "=" * 70)
            print("Loading existing classifications...")
            print("=" * 70)
            existing_classifications = pd.read_csv(gemini_classification_path)
            print(f"✓ Loaded {len(existing_classifications)} existing classifications")

            # Get set of already classified url_hash values
            existing_url_hashes = set(existing_classifications["url_hash"].unique())
            print(
                f"✓ Found {len(existing_url_hashes)} unique url_hash entries already classified"
            )

            # Identify new products (url_hash not in existing classifications)
            new_products_mask = ~df_products_input["url_hash"].isin(existing_url_hashes)
            df_new_products = df_products_input[new_products_mask].copy()

            if len(df_new_products) == 0:
                print("\n" + "=" * 70)
                print("✓ No new products to classify")
                print("=" * 70)
                print("All products already have classifications")
                print(f"File location: {gemini_classification_path}")
                print("=" * 70 + "\n")
                return

            print(f"\n✓ Identified {len(df_new_products)} new products to classify")
            print(f"  - Total products: {len(df_products_input)}")
            print(
                f"  - Already classified: {len(df_products_input) - len(df_new_products)}"
            )
            print(f"  - New to classify: {len(df_new_products)}")

            # Use only new products for classification
            df_to_classify = df_new_products
        else:
            print("\n" + "=" * 70)
            print("No existing classifications found")
            print("=" * 70)
            print("Classifying all products...")
            df_to_classify = df_products_input

        # Step 4: Classify new products with Gemini
        # Note: Each batch is now immediately appended to gemini_classification.csv
        print("\n" + "=" * 70)
        print("Classifying products with Gemini AI")
        print("=" * 70)
        df_new_classifications = classify_products_with_gemini(
            df_to_classify,
            df_coicop_no_services,
            df_coicop,
            existing_classifications,
            project_root,
        )
        print(df_new_classifications.head())

        # Batches have already been appended to CSV during classification
        # Print final summary
        print("\n" + "=" * 70)
        print("Classification complete")
        print("=" * 70)

        if gemini_classification_path.exists():
            final_count = len(pd.read_csv(gemini_classification_path))
            if existing_classifications is not None:
                newly_added = final_count - len(existing_classifications)
                print(f"✓ Total classifications in file: {final_count}")
                print(f"  - Previous: {len(existing_classifications)}")
                print(f"  - Newly added: {newly_added}")
            else:
                print(f"✓ Total classifications in file: {final_count}")
        else:
            print(
                "⚠ Warning: No classifications were saved (all batches may have failed)"
            )

        print("\n" + "=" * 70)
        print("✓ COICOP matching workflow completed successfully!")
        print("=" * 70)
        print(
            f"\nOutput files saved to: {project_root / 'data' / 'cpi' / 'coicopping'}"
        )
        print("  - coicop_categories.csv")
        print("  - coicop_categories_no_services.csv")
        print("  - products_input.csv")
        print("  - gemini_classification.csv")
        print("\n")

    except Exception as e:
        print(f"\n✗ Error in workflow: {e}")
        raise


def reclassify_missing_classifications(
    project_root: Path = None,
    batch_size: int = 600,
) -> None:
    """
    Reclassify products in gemini_classification.csv that are missing COICOP codes.

    Args:
        project_root: Optional project root path
        batch_size: Number of products per batch (default 600)
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "prices" / "_enrich"
    gemini_classification_path = data_dir / "gemini_classification.csv"

    # Check if file exists
    if not gemini_classification_path.exists():
        print(f"\n✗ Error: {gemini_classification_path} not found")
        print(
            "Please run the main workflow first to generate gemini_classification.csv"
        )
        return

    print("=" * 80)
    print("RECLASSIFY MISSING COICOP CLASSIFICATIONS")
    print("=" * 80)

    # Step 1: Read gemini_classification.csv
    print("\n1. Reading gemini_classification.csv...")
    df_classifications = pd.read_csv(gemini_classification_path)
    print(f"✓ Loaded {len(df_classifications)} total classifications")

    # Step 2: Find rows without coicop_code and coicop_title
    print("\n2. Finding rows without classifications...")
    missing_mask = (
        df_classifications["coicop_code"].isna()
        | df_classifications["coicop_title"].isna()
    )
    df_missing = df_classifications[missing_mask].copy()
    df_classified = df_classifications[~missing_mask].copy()

    print(f"✓ Found {len(df_missing)} rows without classifications")
    print(f"✓ Found {len(df_classified)} rows already classified")

    if len(df_missing) == 0:
        print("\n✓ All rows already have classifications. Nothing to do!")
        return

    # Step 3: Load COICOP categories
    print("\n3. Loading COICOP categories...")
    excel_path = data_dir / "coicop_categories.xlsx"
    if not excel_path.exists():
        print(f"✗ Error: {excel_path} not found")
        print("Please run the main workflow first to download COICOP data")
        return

    df_coicop = load_and_process_coicop(excel_path, digit_level=4)
    df_coicop_no_services = df_coicop[
        ~df_coicop["coicop_code"].str.endswith(" (S)")
    ].copy()
    print(f"✓ Loaded {len(df_coicop_no_services)} COICOP categories (no services)")

    # Step 4: Reclassify missing products
    print(f"\n4. Reclassifying {len(df_missing)} products...")
    try:
        import google.generativeai as genai
    except ImportError:
        print("\n✗ ERROR: google-generativeai library not installed")
        print("Install it with: pip install google-generativeai")
        return

    # Setup API
    api_key = setup_google_api_key()
    genai.configure(api_key=api_key)

    # Prepare unique products to classify
    unique_products = (
        df_missing[["product_w_cat"]].drop_duplicates().reset_index(drop=True)
    )
    total_products = len(unique_products)
    num_batches = (total_products + batch_size - 1) // batch_size

    print(
        f"\nClassifying {total_products} unique products in {num_batches} batches (batch size: {batch_size})"
    )

    all_results = []

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_products)
        batch_products = unique_products.iloc[start_idx:end_idx][
            "product_w_cat"
        ].tolist()

        print(
            f"\nBatch {batch_num + 1}/{num_batches}: Processing {len(batch_products)} products..."
        )

        # Format prompt
        prompt = format_gemini_prompt(batch_products, df_coicop_no_services)

        # Call Gemini API
        try:
            model = genai.GenerativeModel("gemini-3.1-flash-lite")
            response = model.generate_content(prompt)
            response_text = response.text

            # Parse CSV response
            batch_results = parse_gemini_response(response_text)
            all_results.extend(batch_results)

            if len(batch_results) == 0:
                print(f"⚠ Batch {batch_num + 1}: No valid results parsed.")
                print(f"  Response preview (first 300 chars):\n{response_text[:300]}")

            print(f"✓ Batch {batch_num + 1}: Classified {len(batch_results)} products")

        except Exception as e:
            error_msg = str(e).lower()
            # Check for quota exceeded errors
            if (
                "quota" in error_msg
                or "resource_exhausted" in error_msg
                or "429" in error_msg
            ):
                print(f"\n✗ API quota exceeded at batch {batch_num + 1}/{num_batches}")
                print(f"  Error: {e}")
                print("\n⚠ Stopping remaining batches")
                break
            else:
                print(f"✗ Error processing batch {batch_num + 1}: {e}")
                continue

    if not all_results:
        print("\n✗ Error: No products were successfully classified")
        return

    df_new_classifications = pd.DataFrame(all_results)
    print(f"\n✓ Total newly classified: {len(df_new_classifications)} products")

    # Step 5: Merge with COICOP categories to get titles
    print("\n5. Adding COICOP titles...")
    df_new_classifications = df_new_classifications.merge(
        df_coicop[["coicop_code", "coicop_title"]],
        on="coicop_code",
        how="left",
    )

    # Step 6: Update missing rows with new classifications
    print("\n6. Updating missing rows with new classifications...")

    # Merge new classifications back to missing rows (including confidence if present)
    merge_cols = ["product_w_cat", "coicop_code", "coicop_title"]
    if "confidence" in df_new_classifications.columns:
        merge_cols.append("confidence")

    df_missing_updated = df_missing.merge(
        df_new_classifications[merge_cols],
        on="product_w_cat",
        how="left",
        suffixes=("_old", ""),
    )

    # Drop old columns if they exist
    cols_to_drop = [col for col in df_missing_updated.columns if col.endswith("_old")]
    if cols_to_drop:
        df_missing_updated = df_missing_updated.drop(columns=cols_to_drop)

    # Step 7: Combine all rows
    print("\n7. Combining all rows...")
    df_final = pd.concat([df_classified, df_missing_updated], ignore_index=True)

    # Remove duplicates (keep first)
    df_final = df_final.drop_duplicates(
        subset=["url_hash", "product_w_cat"], keep="first"
    )

    print(f"✓ Final dataframe: {len(df_final)} rows")

    # Step 8: Save updated gemini_classification.csv
    print("\n8. Saving updated gemini_classification.csv...")
    df_final.to_csv(gemini_classification_path, index=False)
    print(f"✓ Saved to {gemini_classification_path}")

    # Print summary
    still_missing = df_final["coicop_code"].isna().sum()
    classified_count = df_final["coicop_code"].notna().sum()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total rows: {len(df_final)}")
    print(f"Classified rows: {classified_count}")
    print(f"Still missing: {still_missing}")

    if still_missing > 0:
        print(f"\n⚠ Warning: {still_missing} rows still missing classifications")
        print("These products may have failed during API calls or parsing")
    else:
        print("\n✓ SUCCESS: All rows now have COICOP classifications!")

    print("=" * 80)


if __name__ == "__main__":
    project_root = get_project_root()
    data_dir = project_root / "data" / "prices" / "_enrich"

    # Run COICOP matching workflow
    run_coicop_matching(project_root)

    # Extract quantities and merge with COICOP classifications
    gemini_classification_path = data_dir / "gemini_classification.csv"
    df_merged = extract_and_merge_quantities(
        project_root=project_root,
        gemini_classification_path=gemini_classification_path,
    )

    # Save merged data to CSV if gemini_classification.csv exists
    if gemini_classification_path.exists():
        output_path = data_dir / "unit_values_w_categories.csv"
        df_merged.to_csv(output_path, index=False)
        print(f"✓ Saved to {output_path}")
