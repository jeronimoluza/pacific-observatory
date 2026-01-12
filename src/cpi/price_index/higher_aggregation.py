"""
Higher-Level Aggregation for CPI Construction.

Implements the Young Index aggregation using HIES expenditure weights.
Combines elementary aggregate indices into Division 01 (Food and non-alcoholic beverages).
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.redistribute_weights import (
        redistribute_weights,
        validate_weights,
    )
else:
    from .redistribute_weights import redistribute_weights, validate_weights


# COICOP code to category name mapping
COICOP_CATEGORY_MAP = {
    "01.1.1": "Cereals",
    "01.1.2": "Meats",
    "01.1.3": "Seafood",
    "01.1.4": "Dairy",
    "01.1.5": "Oils",
    "01.1.6": "Fruits",
    "01.1.7": "Vegetables",
    "01.1.8": "Sugars",
    "01.1.9": "Other foods",
    "01.2": "Beverages",
    "01.2.1": "Beverages (Juices)",
    "01.2.2": "Beverages (Coffee)",
}


def load_weights() -> pd.DataFrame:
    """
    Load and prepare HIES expenditure weights.

    Uses the redistribute_weights module to get normalized weights
    with Food Away from Home redistributed.

    Returns:
        DataFrame with columns: coicop_code, category, weight
    """
    print("Loading HIES expenditure weights...")

    # Get redistributed and normalized weights
    df_raw = redistribute_weights()
    _, df_normalized = validate_weights(df_raw)

    # Filter out Food Away from Home and prepare
    weights = df_normalized[
        df_normalized["Food Breakdown"] != "Food Away from Home"
    ].copy()

    weights = weights.rename(
        columns={
            "COICOP Code": "coicop_code",
            "Food Breakdown": "category",
            "Adjusted Weights": "weight",
        }
    )

    # Convert weight to decimal (0-1 scale)
    weights["weight_decimal"] = weights["weight"] / 100.0

    weights = weights[["coicop_code", "category", "weight", "weight_decimal"]]

    print(f"  - {len(weights)} categories with weights")
    print(f"  - Total weight: {weights['weight'].sum():.2f}%")

    return weights


def map_ea_to_weights(
    jevons_indices: pd.DataFrame,
    weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Map elementary aggregate indices to expenditure weights.

    Handles mapping between 3-digit COICOP codes in the data
    and the weight categories (which may be at different levels).

    Args:
        jevons_indices: DataFrame with Jevons indices by EA and month
        weights: DataFrame with expenditure weights

    Returns:
        DataFrame with EA indices and their corresponding weights
    """
    print("Mapping elementary aggregates to weights...")

    # Get unique EAs from the data
    eas = jevons_indices["coicop_3digit"].unique()

    # Create mapping
    ea_weight_map = []
    for ea in eas:
        # Try exact match first
        weight_row = weights[weights["coicop_code"] == ea]

        if len(weight_row) == 0:
            # Try parent category (e.g., 01.2.1 -> 01.2)
            parent = ".".join(ea.split(".")[:2])
            weight_row = weights[weights["coicop_code"] == parent]

        if len(weight_row) > 0:
            ea_weight_map.append(
                {
                    "coicop_3digit": ea,
                    "weight_category": weight_row.iloc[0]["coicop_code"],
                    "category_name": weight_row.iloc[0]["category"],
                    "weight": weight_row.iloc[0]["weight"],
                    "weight_decimal": weight_row.iloc[0]["weight_decimal"],
                }
            )
        else:
            print(f"  WARNING: No weight found for EA {ea}")
            ea_weight_map.append(
                {
                    "coicop_3digit": ea,
                    "weight_category": None,
                    "category_name": COICOP_CATEGORY_MAP.get(ea, "Unknown"),
                    "weight": 0.0,
                    "weight_decimal": 0.0,
                }
            )

    ea_weights = pd.DataFrame(ea_weight_map)

    # Merge with Jevons indices
    merged = jevons_indices.merge(ea_weights, on="coicop_3digit", how="left")

    matched = merged[merged["weight"] > 0]["coicop_3digit"].nunique()
    print(f"  - {matched}/{len(eas)} EAs matched to weights")

    return merged


def compute_young_index(
    ea_with_weights: pd.DataFrame,
    reference_month: str,
) -> pd.DataFrame:
    """
    Compute the Young Index for Division 01.

    The Young Index uses fixed base-period weights applied to
    current period price indices:

    I_Young,t = Σ w_{2019-20,k} × J_{k,t}

    Args:
        ea_with_weights: DataFrame with EA indices and weights
        reference_month: Reference month string

    Returns:
        DataFrame with Young Index by month
    """
    print("Computing Young Index...")

    # Compute weighted contribution for each EA
    ea_with_weights = ea_with_weights.copy()
    ea_with_weights["weighted_contribution"] = (
        ea_with_weights["weight_decimal"] * ea_with_weights["jevons_index_100"]
    )

    # Aggregate by month
    young_index = (
        ea_with_weights.groupby("month")
        .agg(
            young_index=("weighted_contribution", "sum"),
            n_eas=("coicop_3digit", "nunique"),
            total_weight=("weight_decimal", "sum"),
        )
        .reset_index()
    )

    # Normalize by total weight (in case some EAs are missing)
    young_index["young_index_normalized"] = (
        young_index["young_index"] / young_index["total_weight"]
    )

    # Add reference month flag
    young_index["is_reference"] = young_index["month"] == reference_month

    print(f"  - {len(young_index)} months")
    ref_value = young_index[young_index["is_reference"]][
        "young_index_normalized"
    ].values
    if len(ref_value) > 0:
        print(f"  - Reference month ({reference_month}): {ref_value[0]:.2f}")
    print(f"  - Latest month: {young_index['young_index_normalized'].iloc[-1]:.2f}")

    return young_index


def compute_weighted_contributions(
    ea_with_weights: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute weighted contribution of each EA to the overall index.

    This shows how much each category contributes to the total CPI.

    Args:
        ea_with_weights: DataFrame with EA indices and weights

    Returns:
        DataFrame with weighted contributions by EA and month
    """
    df = ea_with_weights.copy()

    # Weighted contribution
    df["weighted_contribution"] = df["weight_decimal"] * df["jevons_index_100"]

    # Select relevant columns
    contributions = df[
        [
            "month",
            "coicop_3digit",
            "category_name",
            "weight",
            "jevons_index_100",
            "weighted_contribution",
            "n_articles",
        ]
    ].copy()

    return contributions


def compute_higher_aggregation(
    jevons_indices: pd.DataFrame,
    reference_month: str,
    weights: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Compute higher-level aggregation using Young Index.

    This is the main entry point for higher-level aggregation.

    Args:
        jevons_indices: DataFrame with Jevons indices from elementary_aggregates
        reference_month: Reference month string
        weights: Optional pre-loaded weights DataFrame

    Returns:
        Tuple of:
        - young_index: Division 01 index by month
        - ea_with_weights: EA indices with weights
        - contributions: Weighted contributions by EA
        - stats: Computation statistics
    """
    print("\n" + "=" * 60)
    print("HIGHER-LEVEL AGGREGATION")
    print("=" * 60)

    stats = {}

    # Load weights if not provided
    if weights is None:
        weights = load_weights()

    stats["n_weight_categories"] = len(weights)

    # Map EAs to weights
    ea_with_weights = map_ea_to_weights(jevons_indices, weights)
    stats["n_eas_matched"] = ea_with_weights[ea_with_weights["weight"] > 0][
        "coicop_3digit"
    ].nunique()

    # Compute Young Index
    young_index = compute_young_index(ea_with_weights, reference_month)
    stats["n_months"] = len(young_index)

    # Compute weighted contributions
    contributions = compute_weighted_contributions(ea_with_weights)

    # Summary stats (use normalized index which has reference month = 100)
    ref_row = young_index[young_index["is_reference"]]
    if len(ref_row) > 0:
        stats["ref_index"] = ref_row["young_index_normalized"].values[0]

    stats["latest_index"] = young_index["young_index_normalized"].iloc[-1]
    stats["min_index"] = young_index["young_index_normalized"].min()
    stats["max_index"] = young_index["young_index_normalized"].max()

    print("=" * 60 + "\n")

    return young_index, ea_with_weights, contributions, stats


def get_category_summary(contributions: pd.DataFrame) -> pd.DataFrame:
    """
    Generate summary by category across all months.

    Args:
        contributions: Weighted contributions DataFrame

    Returns:
        Summary DataFrame with one row per category
    """
    summary = (
        contributions.groupby(["coicop_3digit", "category_name", "weight"])
        .agg(
            avg_index=("jevons_index_100", "mean"),
            min_index=("jevons_index_100", "min"),
            max_index=("jevons_index_100", "max"),
            avg_contribution=("weighted_contribution", "mean"),
            avg_articles=("n_articles", "mean"),
        )
        .reset_index()
        .sort_values("weight", ascending=False)
    )

    return summary
