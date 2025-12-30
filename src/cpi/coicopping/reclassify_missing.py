"""
Reclassify missing COICOP classifications in gemini_classification.csv.

This script:
1. Reads gemini_classification.csv
2. Finds all rows without coicop_code and coicop_title
3. Reclassifies those products using Gemini API
4. Merges reclassified rows back into the dataframe
5. Saves the updated gemini_classification.csv with all rows classified
"""

import sys
from pathlib import Path

import pandas as pd

# Handle both relative and direct execution
try:
    from .coicop_categories import load_and_process_coicop
    from .coicop_matching import (
        setup_google_api_key,
        format_gemini_prompt,
        parse_gemini_response,
        get_project_root,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from coicop_categories import load_and_process_coicop
    from coicop_matching import (
        setup_google_api_key,
        format_gemini_prompt,
        parse_gemini_response,
        get_project_root,
    )


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

    data_dir = project_root / "data" / "cpi" / "coicopping"
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
            model = genai.GenerativeModel("gemini-3-flash-preview")
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

    # Merge new classifications back to missing rows
    df_missing_updated = df_missing.merge(
        df_new_classifications[["product_w_cat", "coicop_code", "coicop_title"]],
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
    reclassify_missing_classifications()
