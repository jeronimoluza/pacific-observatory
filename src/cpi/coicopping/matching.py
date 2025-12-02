"""Match products to COICOP categories using fuzzy matching.

This module performs fuzzy matching of product names (product_w_cat) against
COICOP category keywords to assign each product to its most likely category.

Workflow:
1. Load COICOP categories with keywords_list
2. Prepare matching data (product_w_cat, url_hash)
3. Deduplicate on (product_w_cat, url_hash) pairs
4. Fuzzy match each product_w_cat against all keywords
5. Assign COICOP code with highest score (minimum 70)
6. Add results back to all original rows
"""

import sys
from pathlib import Path
from typing import Optional, Tuple
import logging

import pandas as pd
from thefuzz import process

# Handle both relative and direct execution
try:
    from .coicop_categories import get_coicop_categories
    from .prestep import prepare_coicop_matching_data
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from coicop_categories import get_coicop_categories
    from prestep import prepare_coicop_matching_data


logger = logging.getLogger(__name__)


def fuzzy_match_product_to_coicop(
    product_w_cat: str,
    coicop_df: pd.DataFrame,
    min_score: int = 70
) -> Tuple[Optional[str], int]:
    """
    Fuzzy match a product_w_cat string to a COICOP category.

    Iterates through all keywords in all COICOP categories and finds the
    best match using thefuzz.process.extractOne().

    Args:
        product_w_cat: Product name with category string to match
        coicop_df: DataFrame with COICOP categories (must have 'code' and 'keywords_list' columns)
        min_score: Minimum score threshold (0-100). Returns None if best match is below this.

    Returns:
        Tuple of (coicop_code, score) or (None, score) if no match meets threshold
    """
    if not isinstance(product_w_cat, str) or not product_w_cat.strip():
        return None, 0

    best_match = None
    best_score = 0
    best_code = None

    # Iterate through each COICOP category
    for _, row in coicop_df.iterrows():
        code = row['code']
        keywords_list = row['keywords_list']

        # Skip if keywords_list is empty or not a list
        if not isinstance(keywords_list, list) or not keywords_list:
            continue

        # Fuzzy match product_w_cat against all keywords in this category
        match_result = process.extractOne(product_w_cat, keywords_list)

        if match_result is None:
            continue

        matched_keyword, score = match_result

        # Track the best match across all categories
        if score > best_score:
            best_score = score
            best_match = matched_keyword
            best_code = code

    # Return code and score only if score meets minimum threshold
    if best_score >= min_score:
        return best_code, best_score
    else:
        return None, best_score


def match_products_to_coicop(
    products_df: pd.DataFrame,
    coicop_df: pd.DataFrame,
    min_score: int = 70
) -> pd.DataFrame:
    """
    Match all products to COICOP categories using fuzzy matching.

    Deduplicates on (product_w_cat, url_hash) pairs, performs fuzzy matching,
    and adds results back to all original rows.

    Args:
        products_df: DataFrame with products (must have 'product_w_cat' and 'url_hash' columns)
        coicop_df: DataFrame with COICOP categories
        min_score: Minimum score threshold (0-100)

    Returns:
        DataFrame with original rows plus 'coicop_code' and 'match_score' columns
    """
    # Create a copy to avoid modifying original
    df = products_df.copy()

    # Deduplicate on (product_w_cat, url_hash) pairs
    unique_pairs = df[['product_w_cat', 'url_hash']].drop_duplicates().reset_index(drop=True)
    logger.info(f"Deduplicating: {len(df)} rows → {len(unique_pairs)} unique (product_w_cat, url_hash) pairs")

    # Perform fuzzy matching on unique pairs
    matches = []
    for idx, row in unique_pairs.iterrows():
        product_w_cat = row['product_w_cat']
        url_hash = row['url_hash']

        # Fuzzy match this product
        coicop_code, score = fuzzy_match_product_to_coicop(product_w_cat, coicop_df, min_score)

        matches.append({
            'product_w_cat': product_w_cat,
            'url_hash': url_hash,
            'coicop_code': coicop_code,
            'match_score': score
        })

        if (idx + 1) % 100 == 0:
            logger.info(f"Matched {idx + 1}/{len(unique_pairs)} unique products")

    # Create matches DataFrame
    matches_df = pd.DataFrame(matches)
    logger.info(f"Matching complete. Matched products: {(matches_df['coicop_code'].notna()).sum()}/{len(matches_df)}")

    # Merge results back to original DataFrame
    df = df.merge(
        matches_df[['product_w_cat', 'url_hash', 'coicop_code', 'match_score']],
        on=['product_w_cat', 'url_hash'],
        how='left'
    )

    return df


def run_coicop_matching(project_root: Optional[Path] = None, min_score: int = 70) -> pd.DataFrame:
    """
    Main function to run the complete COICOP matching workflow.

    Steps:
    1. Load COICOP categories
    2. Prepare product matching data
    3. Perform fuzzy matching
    4. Return results

    Args:
        project_root: Optional project root path
        min_score: Minimum score threshold (0-100)

    Returns:
        DataFrame with matched products and COICOP codes
    """
    logger.info("Loading COICOP categories...")
    coicop_df = get_coicop_categories()
    logger.info(f"Loaded {len(coicop_df)} COICOP categories")

    logger.info("Preparing product matching data...")
    products_df = prepare_coicop_matching_data(project_root)
    logger.info(f"Prepared {len(products_df)} products")

    logger.info(f"Starting fuzzy matching with min_score={min_score}...")
    results_df = match_products_to_coicop(products_df, coicop_df, min_score)

    logger.info(f"Matching complete. Results shape: {results_df.shape}")
    logger.info(f"Matched products: {(results_df['coicop_code'].notna()).sum()}/{len(results_df)}")

    return results_df


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run matching
    results = run_coicop_matching(min_score=70)

    # Display results
    print(f"\nMatching Results:")
    print(f"Total rows: {len(results)}")
    print(f"Matched rows: {(results['coicop_code'].notna()).sum()}")
    print(f"Unmatched rows: {(results['coicop_code'].isna()).sum()}")
    print(f"\nColumns: {results.columns.tolist()}")
    print(f"\nSample matched products:")
    matched = results[results['coicop_code'].notna()].head(10)
    print(matched[['product_w_cat', 'coicop_code', 'match_score']])
    print(f"\nSample unmatched products:")
    unmatched = results[results['coicop_code'].isna()].head(5)
    print(unmatched[['product_w_cat', 'match_score']])
    matched.to_csv("matched_products.csv", index=False)
    unmatched.to_csv("unmatched_products.csv", index=False)
