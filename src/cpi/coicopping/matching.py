"""Match products to COICOP categories using fuzzy matching with multiple algorithms.

This module performs fuzzy matching of product names (product_w_cat) against
COICOP category keywords using multiple fuzzy matching algorithms.

Workflow:
1. Load COICOP categories and create keywords column (lowercase, normalized, no stopwords)
2. Prepare matching data (product_w_cat, url_hash)
3. For each product_w_cat, apply all fuzzy matching algorithms
4. For each algorithm, select the highest scoring match
5. Output results with predictions from all algorithms
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import unicodedata
import re

import pandas as pd
from thefuzz import process
from thefuzz import fuzz
from tqdm import tqdm

# Handle both relative and direct execution
try:
    from .coicop_categories import get_coicop_categories
    from .prestep import prepare_coicop_matching_data
    from .regex_config import STOPWORDS
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from coicop_categories import get_coicop_categories
    from prestep import prepare_coicop_matching_data
    from regex_config import STOPWORDS


def normalize_text(text: str) -> str:
    """
    Normalize text for keyword creation.
    
    Steps (in order):
    1. Remove x000d encoding artifacts
    2. Convert to lowercase
    3. Remove accents (é → e, ñ → n, etc.)
    4. Remove special characters and numbers (keep only letters and spaces)
    5. Remove stopwords
    6. Clean up extra whitespace
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    if not isinstance(text, str):
        return ""
    
    # Step 1: Remove x000d encoding artifacts
    text = re.sub(r'_x000D_', '', text)
    
    # Step 2: Lowercase
    text = text.lower()
    
    # Step 3: Remove accents (normalize to NFD, then remove combining characters)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    
    # Step 4: Remove special characters and numbers (keep only letters and spaces)
    text = re.sub(r'[^a-z\s]', ' ', text)
    
    # Step 5: Split into words and remove stopwords
    words = text.split()
    words = [word for word in words if word and word not in STOPWORDS]
    
    # Step 6: Clean up extra whitespace
    text = ' '.join(words)
    
    return text


def create_coicop_keywords(coicop_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create keywords column from all_info for each COICOP category.
    
    Applies normalize_text() to all_info column and creates a "keywords" column.
    
    Args:
        coicop_df: DataFrame with COICOP categories (must have 'all_info' column)
        
    Returns:
        DataFrame with 'code', 'title', and 'keywords' columns
    """
    df = coicop_df[['code', 'title', 'keywords']].copy()
    df['keywords'] = df['keywords'].apply(normalize_text)
    df = df[['code', 'title', 'keywords']]
    
    print(f"✓ Created keywords for {len(df)} COICOP categories")
    return df


def fuzzy_match_with_algorithm(
    product_w_cat: str,
    coicop_keywords_list: List[str],
    scorer
) -> Tuple[Optional[str], int]:
    """
    Fuzzy match a product against COICOP keywords using a specific algorithm.
    
    Args:
        product_w_cat: Product name to match
        coicop_keywords_list: List of COICOP keywords to match against
        scorer: Fuzzy matching algorithm (e.g., fuzz.ratio, fuzz.token_set_ratio)
        
    Returns:
        Tuple of (best_keyword, best_score) or (None, 0) if no match
    """
    product_w_cat = normalize_text(product_w_cat)
    if not isinstance(product_w_cat, str) or not product_w_cat.strip():
        return None, 0
    
    if not coicop_keywords_list:
        return None, 0
    
    # Use process.extractOne to find best match with specific scorer
    match_result = process.extractOne(
        product_w_cat,
        coicop_keywords_list,
        scorer=scorer
    )
    
    if match_result is None:
        return None, 0
    
    matched_keyword, score = match_result
    return matched_keyword, score


def match_product_with_all_algorithms(
    product_w_cat: str,
    coicop_df: pd.DataFrame
) -> Dict[str, Tuple[str, str, int]]:
    """
    Match a product against COICOP categories using all available algorithms.
    
    For each algorithm, finds the best matching COICOP category and returns
    (title, code, score) for that algorithm.
    
    Args:
        product_w_cat: Product name to match
        coicop_df: DataFrame with COICOP categories (must have 'code', 'title', 'keywords' columns)
        
    Returns:
        Dictionary with algorithm names as keys and (title, code, score) tuples as values
    """
    if not isinstance(product_w_cat, str) or not product_w_cat.strip():
        return {}
    
    # List of all available fuzzy matching algorithms
    algorithms = {
        'ratio': fuzz.ratio,
        'partial_ratio': fuzz.partial_ratio,
        'token_sort_ratio': fuzz.token_sort_ratio,
        'token_set_ratio': fuzz.token_set_ratio,
        'partial_token_sort_ratio': fuzz.partial_token_sort_ratio,
    }
    
    results = {}
    
    for algo_name, scorer in algorithms.items():
        best_score = 0
        best_code = None
        best_title = None
        
        # Iterate through each COICOP category
        for _, row in coicop_df.iterrows():
            code = row['code']
            title = row['title']
            keywords = row['keywords']
            
            # Skip if keywords is empty
            if not isinstance(keywords, str) or not keywords.strip():
                continue
            
            # Split keywords into list for matching
            keywords_list = keywords.split()
            
            # Fuzzy match against this category's keywords
            matched_keyword, score = fuzzy_match_with_algorithm(
                product_w_cat,
                keywords_list,
                scorer
            )
            
            # Track best match for this algorithm
            if score > best_score:
                best_score = score
                best_code = code
                best_title = title
        
        # Store result for this algorithm
        if best_code is not None:
            results[algo_name] = (best_title, best_code, best_score)
    
    return results


def match_products_to_coicop_multi_algorithm(
    products_df: pd.DataFrame,
    coicop_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Match all products to COICOP categories using multiple algorithms.
    
    For each product, applies all fuzzy matching algorithms and creates columns
    for each algorithm's predictions.
    
    Args:
        products_df: DataFrame with products (must have 'product_w_cat' column)
        coicop_df: DataFrame with COICOP categories
        
    Returns:
        DataFrame with product_w_cat and prediction columns for each algorithm
    """
    df = products_df[['product_w_cat']].copy()
    
    # Get unique products for matching
    unique_products = df['product_w_cat'].unique()
    print(f"Matching {len(unique_products)} unique products against COICOP categories...")
    
    # Match each unique product
    all_results = {}
    for product in tqdm(unique_products, desc="Matching products"):
        if not isinstance(product, str) or not product.strip():
            all_results[product] = {}
            continue
        
        algo_results = match_product_with_all_algorithms(product, coicop_df)
        all_results[product] = algo_results
    
    # Create result columns for each algorithm
    algorithms = ['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'partial_token_sort_ratio']
    
    for algo in algorithms:
        col_name = f'predicted_{algo}'
        df[col_name] = df['product_w_cat'].apply(
            lambda x: (
                f"{all_results[x][algo][0]}; {all_results[x][algo][1]}"
                if algo in all_results.get(x, {})
                else None
            )
        )
    
    print(f"✓ Matching complete. Results shape: {df.shape}")
    
    return df


def run_coicop_matching(
    project_root: Optional[Path] = None,
    digit_level: int = 3
) -> pd.DataFrame:
    """
    Main function to run the complete COICOP matching workflow with multiple algorithms.
    
    Steps:
    1. Load COICOP categories at specified digit level
    2. Create keywords column (normalized, no stopwords)
    3. Prepare product matching data
    4. Match products using all fuzzy matching algorithms
    5. Return results with predictions from all algorithms
    
    Args:
        project_root: Optional project root path
        digit_level: COICOP digit level (number of dots in code)
        
    Returns:
        DataFrame with product_w_cat and algorithm predictions
    """
    print(f"Loading COICOP categories at digit level {digit_level}...")
    coicop_df = get_coicop_categories(digit_level=digit_level)
    print(f"✓ Loaded {len(coicop_df)} COICOP categories at digit level {digit_level}")
    
    print("Creating keywords column...")
    coicop_df = create_coicop_keywords(coicop_df)
    coicop_df.to_csv("coicop_categories.csv", index=False)
    
    print("Preparing product matching data...")
    products_df = prepare_coicop_matching_data(project_root)
    print(f"✓ Prepared {len(products_df)} products")
    
    print("Starting multi-algorithm fuzzy matching...")
    results_df = match_products_to_coicop_multi_algorithm(products_df, coicop_df)
    
    print(f"✓ Matching complete. Results shape: {results_df.shape}")
    
    return results_df


if __name__ == "__main__":
    # Parameter: digit level (number of dots in COICOP code)
    digit_level = 3
    
    # Run matching
    results = run_coicop_matching(digit_level=digit_level)
    
    # Display results
    print(f"\nMatching Results:")
    print(f"Total rows: {len(results)}")
    print(f"Columns: {results.columns.tolist()}")
    print(f"\nFirst 10 rows:")
    print(results.head(10))
    
    # Save results
    results.to_csv("coicop_matching_results.csv", index=False)
    print(f"\nResults saved to coicop_matching_results.csv")
