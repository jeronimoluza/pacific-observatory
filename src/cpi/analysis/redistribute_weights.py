"""
Weight Redistribution Script for CPI Analysis

Redistributes the "Food Away from Home" weight (4.3%) proportionally
to other food categories based on their original expenditure shares.

The redistribution formula is:
    adjusted_weight = original_weight × (1 + food_away_from_home_weight / 100)
"""

import pandas as pd


def redistribute_weights():
    """
    Redistribute the 4.3% "Food Away from Home" weight proportionally
    to other food categories.

    Returns:
        pd.DataFrame: DataFrame with original and adjusted weights
    """

    # Original HIES 2019-20 weights
    weights_data = {
        "Food Breakdown": [
            "Vegetables",
            "Cereals",
            "Meats",
            "Seafood",
            "Dairy",
            "Oils",
            "Sugars",
            "Food Away from Home",
            "Fruits",
            "Other foods",
            "Beverages",
        ],
        "HIES 2019-20 Expenditure Weights": [
            22.3,
            17.8,
            16.6,
            11.5,
            6.3,
            5.2,
            4.4,
            4.3,
            4.1,
            3.8,
            3.7,
        ],
        "COICOP Code": [
            "01.1.7",
            "01.1.1",
            "01.1.2",
            "01.1.3",
            "01.1.4",
            "01.1.5",
            "01.1.8",
            "–",
            "01.1.6",
            "01.1.9",
            "01.2",
        ],
    }

    df = pd.DataFrame(weights_data)

    # Food Away from Home weight to redistribute
    food_away_from_home_weight = 4.3

    # Multiplicative factor for redistribution
    redistribution_factor = 1 + (food_away_from_home_weight / 100)

    # Calculate adjusted weights
    adjusted_weights = []
    for idx, row in df.iterrows():
        if row["Food Breakdown"] == "Food Away from Home":
            adjusted_weights.append(None)  # Excluded from CPI
        else:
            original = row["HIES 2019-20 Expenditure Weights"]
            adjusted = original * redistribution_factor
            adjusted_weights.append(round(adjusted, 5))

    df["Adjusted Weights"] = adjusted_weights

    # Reorder columns for clarity
    df = df[
        [
            "Food Breakdown",
            "HIES 2019-20 Expenditure Weights",
            "Adjusted Weights",
            "COICOP Code",
        ]
    ]

    return df


def validate_weights(df):
    """
    Validate that adjusted weights (excluding Food Away from Home) sum to 100%.
    Normalizes weights to ensure they sum to exactly 100%.

    Args:
        df (pd.DataFrame): DataFrame with adjusted weights

    Returns:
        tuple: (validation_dict, normalized_df with final weights)
    """

    # Sum of original weights (excluding Food Away from Home)
    original_sum = df[df["Food Breakdown"] != "Food Away from Home"][
        "HIES 2019-20 Expenditure Weights"
    ].sum()

    # Normalize adjusted weights to sum to exactly 100%
    df_normalized = df.copy()
    adjusted_weights_df = df_normalized[
        df_normalized["Food Breakdown"] != "Food Away from Home"
    ].copy()
    total = adjusted_weights_df["Adjusted Weights"].sum()
    normalized_weights = (adjusted_weights_df["Adjusted Weights"] / total * 100).round(
        2
    )

    # Update the dataframe with normalized weights
    for idx in normalized_weights.index:
        df_normalized.loc[idx, "Adjusted Weights"] = normalized_weights[idx]

    adjusted_sum = df_normalized[
        df_normalized["Food Breakdown"] != "Food Away from Home"
    ]["Adjusted Weights"].sum()

    validation_results = {
        "original_sum": round(original_sum, 2),
        "adjusted_sum": round(adjusted_sum, 2),
        "food_away_from_home_weight": 4.3,
        "total_original_with_fafh": round(original_sum + 4.3, 2),
        "is_valid": abs(adjusted_sum - 100.0) < 0.01,
    }

    return validation_results, df_normalized


def main():
    """Main execution function."""

    print("\n" + "=" * 80)
    print("CPI WEIGHT REDISTRIBUTION")
    print("=" * 80)

    # Redistribute weights
    df = redistribute_weights()

    print("\nWeight Redistribution Table (Before Normalization):")
    print("-" * 80)
    print(df.to_string(index=False))

    # Validate and normalize
    validation, df_normalized = validate_weights(df)

    print("\n" + "-" * 80)
    print("Validation Results:")
    print("-" * 80)
    print(
        f"Original weights (excl. Food Away from Home): {validation['original_sum']}%"
    )
    print(
        f"Food Away from Home weight:                   {validation['food_away_from_home_weight']}%"
    )
    print(
        f"Total original:                               {validation['total_original_with_fafh']}%"
    )
    print(
        f"\nAdjusted weights (excl. Food Away from Home): {validation['adjusted_sum']}%"
    )
    print(
        f"Valid redistribution:                         {'✓ YES' if validation['is_valid'] else '✗ NO'}"
    )

    print("\n" + "-" * 80)
    print("Redistribution Formula:")
    print("-" * 80)
    print("adjusted_weight = original_weight × (1 + 4.3/100)")
    print("adjusted_weight = original_weight × 1.043")

    print("\n" + "-" * 80)
    print("Example Calculations (Before Normalization):")
    print("-" * 80)
    for idx, row in df.iterrows():
        if (
            row["Food Breakdown"] != "Food Away from Home"
            and row["Adjusted Weights"] is not None
        ):
            original = row["HIES 2019-20 Expenditure Weights"]
            adjusted = row["Adjusted Weights"]
            print(
                f"{row['Food Breakdown']:15} {original:6.1f}% × 1.043 = {adjusted:6.5f}%"
            )

    print("\n" + "=" * 80)
    print("FINAL NORMALIZED WEIGHTS (Sum = 100%)")
    print("=" * 80)
    print("\n" + df_normalized.to_string(index=False))

    print("\n" + "-" * 80)
    print("Summary:")
    print("-" * 80)
    final_sum = df_normalized[df_normalized["Food Breakdown"] != "Food Away from Home"][
        "Adjusted Weights"
    ].sum()
    print(f"Final adjusted weights sum: {final_sum}%")
    print("=" * 80 + "\n")

    return df_normalized


if __name__ == "__main__":
    df = main()
