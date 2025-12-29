"""
Gemini 2.0 Flash-based COICOP classification workflow.

This module orchestrates the complete workflow:
1. Download COICOP Excel and save processed CSVs
2. Create products_input.csv from price scraping data
3. Classify products using Gemini 2.0 Flash in batches of 2000
4. Generate final gemini_classification.csv with code and title mappings
"""

import os
import sys
import csv
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import pandas as pd

# Handle both relative and direct execution
try:
    from .coicop_categories import (
        download_coicop_excel,
        load_and_process_coicop,
    )
    from .prestep import prepare_coicop_matching_data
    from .extract_quantities import extract_quantities
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from coicop_categories import (
        download_coicop_excel,
        load_and_process_coicop,
    )
    from prestep import prepare_coicop_matching_data
    from extract_quantities import extract_quantities


def get_project_root(current_file: Path = None) -> Path:
    """Get the project root directory."""
    if current_file is None:
        current_file = Path(__file__)
    return current_file.parent.parent.parent.parent


def setup_google_api_key() -> str:
    """
    Check if GOOGLE_API_KEY is set in environment variables.
    If not, provide setup instructions and exit.

    Returns:
        The Google API key

    Raises:
        ValueError: If GOOGLE_API_KEY is not set
    """
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        print("\n" + "=" * 70)
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("=" * 70)
        print("\nTo use Gemini 2.0 Flash for COICOP classification, you need to:")
        print("\n1. Get your API key from: https://aistudio.google.com/apikey")
        print("\n2. Set it as an environment variable:")
        print("   - On macOS/Linux:")
        print("     export GOOGLE_API_KEY='your-api-key-here'")
        print("     python src/cpi/coicopping/coicop_matching.py")
        print("\n   - Or set it in your shell profile (~/.zshrc, ~/.bash_profile):")
        print("     echo \"export GOOGLE_API_KEY='your-api-key-here'\" >> ~/.zshrc")
        print("     source ~/.zshrc")
        print("\n   - On Windows (PowerShell):")
        print("     $env:GOOGLE_API_KEY='your-api-key-here'")
        print("     python src/cpi/coicopping/coicop_matching.py")
        print("\n3. Or pass it directly:")
        print(
            "   GOOGLE_API_KEY='your-api-key-here' python src/cpi/coicopping/coicop_matching.py"
        )
        print("=" * 70 + "\n")
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    return api_key


def download_and_save_coicop_data(
    project_root: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Download COICOP Excel file and save processed CSVs.

    Saves:
    - data/cpi/coicopping/coicop_categories.csv
    - data/cpi/coicopping/coicop_categories_no_services.csv

    Args:
        project_root: Optional project root path

    Returns:
        Tuple of (full_df, no_services_df)
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "cpi" / "coicopping"

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
    df[["code", "title", "keywords"]].to_csv(csv_path, index=False)
    print(f"✓ Saved to {csv_path}")

    # Save categories without services (only code, title, keywords columns)
    df_no_services = df[~df["code"].str.endswith(" (S)")].copy()
    csv_no_services_path = data_dir / "coicop_categories_no_services.csv"
    df_no_services[["code", "title", "keywords"]].to_csv(
        csv_no_services_path, index=False
    )
    print(
        f"✓ Saved {len(df_no_services)} categories (without services) to {csv_no_services_path}"
    )

    return df, df_no_services


def create_products_input_csv(project_root: Optional[Path] = None) -> pd.DataFrame:
    """
    Create products_input.csv from prepare_coicop_matching_data().

    Extracts url_hash and product_w_cat columns and saves to:
    data/cpi/coicopping/products_input.csv

    Args:
        project_root: Optional project root path

    Returns:
        DataFrame with url_hash and product_w_cat columns
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "cpi" / "coicopping"

    print("\n" + "=" * 70)
    print("STEP 2: Create products_input.csv")
    print("=" * 70)

    print("\nPreparing product data...")
    df_products = prepare_coicop_matching_data(project_root)

    print(f"✓ Prepared {len(df_products)} products")

    # Select required columns
    required_cols = ["url_hash", "product_w_cat"]
    missing_cols = [col for col in required_cols if col not in df_products.columns]

    if missing_cols:
        print(f"Available columns: {df_products.columns.tolist()}")
        raise KeyError(f"Missing columns in prepared data: {missing_cols}")

    df_input = df_products[required_cols].copy()

    # Remove duplicates (keep first occurrence)
    df_input = df_input.drop_duplicates(subset=["product_w_cat"], keep="first")
    print(f"✓ After deduplication: {len(df_input)} unique products")

    # Save to CSV
    csv_path = data_dir / "products_input.csv"
    df_input.to_csv(csv_path, index=False)
    print(f"✓ Saved to {csv_path}")

    return df_input


def format_gemini_prompt(
    batch_products: List[str], coicop_context: pd.DataFrame
) -> str:
    """
    Format the prompt for Gemini 2.0 Flash classification.

    Args:
        batch_products: List of product_w_cat strings (up to 2000)
        coicop_context: DataFrame with COICOP categories (code, title, keywords)

    Returns:
        Formatted prompt string
    """
    # Create COICOP reference text
    coicop_ref = "COICOP CATEGORIES REFERENCE:\n"
    coicop_ref += "Code | Title | Keywords\n"
    coicop_ref += "-" * 100 + "\n"

    for idx, row in coicop_context.iterrows():
        code = row["code"]
        title = row["title"]
        keywords = (
            row["keywords"] if pd.notna(row["keywords"]) else ""
        )  # Truncate for brevity
        coicop_ref += f"{code} | {title} | {keywords}\n"

    # Create products list with explicit mapping
    products_text = "PRODUCTS TO CLASSIFY:\n"
    for i, product in enumerate(batch_products, 1):
        products_text += f"{i}. {product}\n"

    prompt = f"""Classify each product from the products list according to the COICOP categories.

{coicop_ref}

{products_text}

For each product, determine the most appropriate COICOP code based on the keywords and descriptions.

Output ONLY a CSV format with these columns: product_w_cat, code
Do NOT include any other text, explanations, or markdown formatting.
IMPORTANT: The product_w_cat column MUST contain the EXACT product string from the input list above.

Output format example:
product_w_cat,code
"half meter tube; pantry confectionery","01.1.8.9"
"shortbread fingers; pantry biscuit cookies","01.1.1.3"

Start the CSV output immediately with the header row. Include all products from the list."""

    return prompt


def classify_products_with_gemini(
    products_input_df: pd.DataFrame,
    coicop_no_services_df: pd.DataFrame,
    project_root: Optional[Path] = None,
    batch_size: int = 750,
) -> pd.DataFrame:
    """
    Classify products using Gemini 2.0 Flash in batches.

    Args:
        products_input_df: DataFrame with url_hash and product_w_cat
        coicop_no_services_df: COICOP categories (without services)
        project_root: Optional project root path
        batch_size: Number of products per batch (default 500)

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

    print("\n" + "=" * 70)
    print("STEP 3: Classify products with Gemini 2.5 Flash")
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
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            response_text = response.text

            # Parse CSV response
            batch_results = parse_gemini_response(response_text)
            all_results.extend(batch_results)

            # Debug: Show response details if batch is empty
            if len(batch_results) == 0:
                print(f"⚠ Batch {batch_num + 1}: No valid results parsed.")
                print(f"  Response preview (first 300 chars):\n{response_text[:300]}")
                # Check if header is present
                first_line = response_text.split("\n")[0] if response_text else ""
                print(f"  First line: {first_line}")

            print(f"✓ Batch {batch_num + 1}: Classified {len(batch_results)} products")

        except Exception as e:
            print(f"✗ Error processing batch {batch_num + 1}: {e}")
            # Continue with next batch
            continue

    # Combine results
    if not all_results:
        raise ValueError("No products were successfully classified")

    results_df = pd.DataFrame(all_results)
    print(f"\n✓ Total classified: {len(results_df)} products")

    return results_df


def parse_gemini_response(response_text: str) -> List[Dict[str, str]]:
    """
    Parse CSV response from Gemini.

    Args:
        response_text: Raw response text from Gemini (should be CSV format)

    Returns:
        List of dictionaries with product_w_cat, code
    """
    results = []

    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("csv"):
            response_text = response_text[3:]

    response_text = response_text.strip()

    # Handle truncated responses by removing incomplete last row
    # If the last line doesn't end with a quote, it's likely truncated
    lines = response_text.split("\n")
    if lines and not lines[-1].rstrip().endswith('"'):
        # Last row is incomplete, remove it
        lines = lines[:-1]
        response_text = "\n".join(lines)

    # Parse CSV with custom logic to handle inconsistent quoting
    lines = response_text.split("\n")

    # Skip header if present
    start_idx = 0
    if lines and lines[0].startswith("product_w_cat"):
        start_idx = 1

    # Track seen products to avoid duplicates
    seen = set()

    # Parse each line manually to handle inconsistent quoting
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue

        try:
            # Use csv reader to parse individual line
            row_data = list(csv.reader([line]))[0]

            if len(row_data) >= 2:
                product_w_cat = row_data[0].strip() if row_data[0] else None
                code = row_data[1].strip() if row_data[1] else None

                # Only add if we have both fields and haven't seen this product before
                if product_w_cat and code and product_w_cat not in seen:
                    seen.add(product_w_cat)
                    results.append({"product_w_cat": product_w_cat, "code": code})
        except Exception:
            # Skip lines that can't be parsed
            pass

    return results


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

    data_dir = project_root / "data" / "cpi" / "coicopping"

    print("\n" + "=" * 70)
    print("STEP 4: Generate final output")
    print("=" * 70)

    # Merge products with classifications
    merged = products_input_df.merge(
        classification_results_df, on="product_w_cat", how="left"
    )

    # Merge with COICOP categories to get titles
    merged = merged.merge(
        coicop_categories_df[["code", "title"]], on="code", how="left"
    )

    # Select final columns
    final_df = merged[["url_hash", "product_w_cat", "code", "title"]].copy()

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
    classified = final_df[final_df["code"].notna()].shape[0]
    unclassified = final_df[final_df["code"].isna()].shape[0]

    print("\nSummary:")
    print(f"  - Total records: {len(final_df)}")
    print(f"  - Classified: {classified}")
    print(f"  - Unclassified: {unclassified}")

    return final_df


def run_coicop_matching(project_root: Optional[Path] = None) -> None:
    """
    Main orchestration function for the complete COICOP matching workflow.

    Workflow:
    1. Download COICOP Excel and save CSVs
    2. Create products_input.csv
    3. Classify with Gemini 2.0 Flash (batches of 2000)
    4. Generate final gemini_classification.csv

    Args:
        project_root: Optional project root path
    """
    if project_root is None:
        project_root = get_project_root()

    data_dir = project_root / "data" / "cpi" / "coicopping"
    gemini_classification_path = data_dir / "gemini_classification.csv"

    # Check if gemini_classification.csv already exists
    if gemini_classification_path.exists():
        print("\n" + "=" * 70)
        print("✓ gemini_classification.csv already exists")
        print("=" * 70)
        print("Skipping COICOP matching workflow")
        print(f"File location: {gemini_classification_path}")
        print("=" * 70 + "\n")
        return

    try:
        # Step 1: Download and process COICOP data
        df_coicop, df_coicop_no_services = download_and_save_coicop_data(project_root)

        # Step 2: Create products input
        df_products_input = create_products_input_csv(project_root)

        # Step 3: Classify with Gemini
        df_classifications = classify_products_with_gemini(
            df_products_input, df_coicop_no_services, project_root
        )

        # Step 4: Generate final output
        df_final = generate_final_output(
            df_products_input, df_classifications, df_coicop, project_root
        )
        print(df_final.head(5))

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


if __name__ == "__main__":
    project_root = get_project_root()
    data_dir = project_root / "data" / "cpi" / "coicopping"

    # Run COICOP matching workflow
    run_coicop_matching(project_root)

    # Extract quantities from price scraping data
    print("\n" + "=" * 70)
    print("Extracting quantities from price scraping data...")
    print("=" * 70)
    df_quantities = extract_quantities(project_root)
    print(f"✓ Extracted quantities for {len(df_quantities)} products")

    # Load gemini_classification.csv
    gemini_classification_path = data_dir / "gemini_classification.csv"
    if gemini_classification_path.exists():
        print("\nLoading gemini_classification.csv...")
        df_gemini = pd.read_csv(gemini_classification_path)
        print(f"✓ Loaded {len(df_gemini)} classified products")

        # Merge quantities with gemini_classification using url_hash
        print("\nMerging quantities with COICOP classifications...")
        df_quantities_indexed = df_quantities.set_index("url_hash")
        df_gemini_indexed = df_gemini.set_index("url_hash")

        # Join on url_hash with suffix to handle overlapping columns
        df_merged = df_quantities_indexed.join(
            df_gemini_indexed, how="left", rsuffix="_gemini"
        )
        df_merged = df_merged.reset_index()

        print(f"✓ Merged data: {len(df_merged)} records")

        # Save to CSV
        output_path = data_dir / "unit_values_w_categories.csv"
        df_merged.to_csv(output_path, index=False)
        print(f"✓ Saved to {output_path}")

        # Print summary
        print("\nMerged data summary:")
        print(f"  - Total records: {len(df_merged)}")
        print(f"  - Columns: {df_merged.columns.tolist()}")
        print("\nFirst few rows:")
        print(df_merged.head(10))
    else:
        print(
            f"\n⚠ gemini_classification.csv not found at {gemini_classification_path}"
        )
        print("Skipping merge step")
