"""
Elementary Aggregates for CPI Construction.

Implements Steps 1-4 of the CPI methodology:
1. Monthly price averaging by article
2. Price relatives with matched sample rule
3. Imputation for missing articles
4. Jevons index aggregation (geometric mean)

Elementary aggregates are computed at the 3-digit COICOP level.
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Tuple

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.utils import geometric_mean
else:
    from .utils import geometric_mean


def compute_monthly_averages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step 1: Compute monthly average price for each article.

    For each article (url_hash), compute the mean price within each month.

    Formula: p̄_{i,t} = (1/n_t) * Σ p_{i,j,t}

    Args:
        df: Prepared price DataFrame with columns:
            - url_hash: article identifier
            - month: year-month string (YYYY-MM)
            - unit_value: numeric unit value (price per standardized unit)
            - coicop_3digit: 3-digit COICOP code

    Returns:
        DataFrame with monthly average prices per article
    """
    print("Step 1: Computing monthly average prices...")

    # Group by article and month, compute mean price
    monthly_avg = (
        df.groupby(["url_hash", "month", "coicop_3digit", "coicop_code"])
        .agg(
            avg_price=("unit_value", "mean"),
            obs_count=("unit_value", "count"),
            product_name=("product_name", "first"),
        )
        .reset_index()
    )

    print(f"  - {len(monthly_avg):,} article-month observations")
    print(f"  - {monthly_avg['url_hash'].nunique():,} unique articles")

    return monthly_avg


def compute_price_relatives(
    df: pd.DataFrame,
    reference_month: str,
) -> pd.DataFrame:
    """
    Step 2: Compute price relatives with matched sample rule.

    For each article, compute the price relative to the reference month:
    r_{i,t} = p̄_{i,t} / p̄_{i,0}

    Matched Sample Rule: Only include articles that have prices in BOTH
    the current month AND the reference month.

    Args:
        df: Monthly average prices DataFrame
        reference_month: Reference month string (e.g., '2025-11')

    Returns:
        DataFrame with price relatives for matched articles
    """
    print(f"Step 2: Computing price relatives (reference: {reference_month})...")

    # Get reference month prices
    ref_prices = df[df["month"] == reference_month][
        ["url_hash", "avg_price", "coicop_3digit", "coicop_code", "product_name"]
    ].copy()
    ref_prices = ref_prices.rename(columns={"avg_price": "ref_price"})

    if len(ref_prices) == 0:
        raise ValueError(f"No data found for reference month: {reference_month}")

    print(f"  - {len(ref_prices):,} articles in reference month")

    # Get articles that exist in reference month
    ref_articles = set(ref_prices["url_hash"])

    # Filter to matched sample (articles in reference month)
    df_matched = df[df["url_hash"].isin(ref_articles)].copy()

    # Merge with reference prices
    df_matched = df_matched.merge(
        ref_prices[["url_hash", "ref_price"]],
        on="url_hash",
        how="left",
    )

    # Compute price relative
    df_matched["price_relative"] = df_matched["avg_price"] / df_matched["ref_price"]

    # Flag matched vs imputed (all are matched at this point)
    df_matched["is_imputed"] = False

    print(f"  - {len(df_matched):,} matched article-month observations")
    print(f"  - {df_matched['url_hash'].nunique():,} matched articles")

    return df_matched, ref_prices


def impute_missing_prices(
    df_matched: pd.DataFrame,
    ref_prices: pd.DataFrame,
    all_months: list,
    reference_month: str,
) -> pd.DataFrame:
    """
    Step 3: Impute missing prices for articles.

    If an article has a price in the reference month but is missing in
    a given month, impute using the average price change of other
    articles in the same 3-digit COICOP category.

    Formula: p̄_{i,t}^imputed = p̄_{i,0} × r̄_{c,t}

    where r̄_{c,t} is the average price relative of matched articles
    in category c for month t.

    IMPORTANT: Imputation only applies to months >= reference month.
    For months before the reference month, only use matched articles.

    Args:
        df_matched: DataFrame with matched price relatives
        ref_prices: Reference month prices
        all_months: List of all months to include
        reference_month: Reference month string

    Returns:
        DataFrame with matched and imputed price relatives
    """
    print("Step 3: Imputing missing prices...")

    # Calculate average price relative by category and month (for matched articles)
    category_avg_relatives = (
        df_matched.groupby(["coicop_3digit", "month"])["price_relative"]
        .mean()
        .reset_index()
        .rename(columns={"price_relative": "category_avg_relative"})
    )

    # Find missing article-month combinations
    # Only impute for months >= reference month (forward-looking)
    ref_articles = ref_prices["url_hash"].unique()
    months_to_impute = [m for m in all_months if m >= reference_month]

    all_combinations = pd.DataFrame(
        [(a, m) for a in ref_articles for m in months_to_impute],
        columns=["url_hash", "month"],
    )

    # Merge with existing data to find gaps
    existing = df_matched[["url_hash", "month"]].drop_duplicates()
    existing["exists"] = True

    all_combinations = all_combinations.merge(
        existing, on=["url_hash", "month"], how="left"
    )
    missing = all_combinations[all_combinations["exists"].isna()].copy()
    missing = missing.drop(columns=["exists"])

    if len(missing) == 0:
        print("  - No missing prices to impute")
        return df_matched

    print(f"  - {len(missing):,} missing article-month combinations to impute")

    # Add reference prices and category info
    missing = missing.merge(
        ref_prices[
            ["url_hash", "ref_price", "coicop_3digit", "coicop_code", "product_name"]
        ],
        on="url_hash",
        how="left",
    )

    # Add category average relatives
    missing = missing.merge(
        category_avg_relatives,
        on=["coicop_3digit", "month"],
        how="left",
    )

    # Impute price relative using category average
    # If no category average available, use 1.0 (no change)
    missing["price_relative"] = missing["category_avg_relative"].fillna(1.0)
    missing["avg_price"] = missing["ref_price"] * missing["price_relative"]
    missing["is_imputed"] = True
    missing["obs_count"] = 0

    # Drop helper column
    missing = missing.drop(columns=["category_avg_relative"])

    # Combine matched and imputed
    df_combined = pd.concat([df_matched, missing], ignore_index=True)

    imputed_count = missing["is_imputed"].sum()
    print(f"  - Imputed {imputed_count:,} prices")
    print(f"  - Total observations: {len(df_combined):,}")

    return df_combined


def compute_jevons_index(
    df: pd.DataFrame,
    reference_month: str,
) -> pd.DataFrame:
    """
    Step 4: Compute Jevons index for each elementary aggregate.

    The Jevons index is the geometric mean of price relatives:
    J_{EA,t} = exp((1/n) * Σ ln(r_{i,t}))

    Elementary aggregates are defined at the 3-digit COICOP level.

    Args:
        df: DataFrame with price relatives (matched and imputed)
        reference_month: Reference month string

    Returns:
        DataFrame with Jevons indices by 3-digit COICOP and month
    """
    print("Step 4: Computing Jevons indices...")

    # Compute Jevons index by category and month
    jevons_indices = (
        df.groupby(["coicop_3digit", "month"])
        .agg(
            jevons_index=("price_relative", geometric_mean),
            n_articles=("url_hash", "nunique"),
            n_matched=("is_imputed", lambda x: (~x).sum()),
            n_imputed=("is_imputed", "sum"),
        )
        .reset_index()
    )

    # Scale to base 100
    jevons_indices["jevons_index_100"] = jevons_indices["jevons_index"] * 100

    # Add reference month flag
    jevons_indices["is_reference"] = jevons_indices["month"] == reference_month

    print(f"  - {len(jevons_indices):,} category-month indices")
    print(f"  - {jevons_indices['coicop_3digit'].nunique()} elementary aggregates")

    return jevons_indices


def compute_elementary_aggregates(
    df: pd.DataFrame,
    reference_month: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Compute all elementary aggregate indices.

    This is the main entry point for elementary aggregate computation.
    Executes Steps 1-4 of the CPI methodology.

    Args:
        df: Prepared price DataFrame from data_loader
        reference_month: Reference month string (e.g., '2025-11')

    Returns:
        Tuple of:
        - jevons_indices: DataFrame with Jevons indices by EA and month
        - article_relatives: DataFrame with article-level price relatives
        - stats: Dictionary with computation statistics
    """
    print("\n" + "=" * 60)
    print("ELEMENTARY AGGREGATES")
    print("=" * 60)

    stats = {}

    # Step 1: Monthly averages
    monthly_avg = compute_monthly_averages(df)
    stats["monthly_avg_count"] = len(monthly_avg)

    # Step 2: Price relatives with matched sample
    df_matched, ref_prices = compute_price_relatives(monthly_avg, reference_month)
    stats["matched_count"] = len(df_matched)
    stats["ref_articles"] = len(ref_prices)

    # Get all months for imputation
    all_months = sorted(df["month"].unique())
    stats["all_months"] = all_months

    # Step 3: Imputation (only for months >= reference month)
    df_with_imputed = impute_missing_prices(
        df_matched, ref_prices, all_months, reference_month
    )
    stats["imputed_count"] = df_with_imputed["is_imputed"].sum()
    stats["total_with_imputed"] = len(df_with_imputed)

    # Step 4: Jevons indices
    jevons_indices = compute_jevons_index(df_with_imputed, reference_month)
    stats["ea_count"] = jevons_indices["coicop_3digit"].nunique()

    print("=" * 60 + "\n")

    return jevons_indices, df_with_imputed, stats


def get_ea_summary(jevons_indices: pd.DataFrame) -> pd.DataFrame:
    """
    Generate summary of elementary aggregates.

    Args:
        jevons_indices: DataFrame with Jevons indices

    Returns:
        Summary DataFrame with one row per EA
    """
    summary = (
        jevons_indices.groupby("coicop_3digit")
        .agg(
            n_months=("month", "nunique"),
            avg_articles=("n_articles", "mean"),
            min_index=("jevons_index_100", "min"),
            max_index=("jevons_index_100", "max"),
            latest_index=("jevons_index_100", "last"),
        )
        .reset_index()
    )

    return summary
