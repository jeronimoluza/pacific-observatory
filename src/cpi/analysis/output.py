"""
Output Module for CPI Construction.

Exports CPI time series results to various formats.
Generates summary reports and visualizations.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


def export_division_01_index(
    young_index: pd.DataFrame,
    output_dir: str | Path,
    country: str,
    reference_month: str,
) -> Path:
    """
    Export Division 01 (Food and non-alcoholic beverages) CPI index.

    Args:
        young_index: DataFrame with Young Index by month
        output_dir: Output directory path
        country: Country name for filename
        reference_month: Reference month string

    Returns:
        Path to exported CSV file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare output DataFrame
    df = young_index.copy()

    # Use normalized index as the main CPI (this ensures reference month = 100)
    df["cpi_index"] = df["young_index_normalized"]

    # Keep raw index for reference
    df["cpi_index_raw"] = df["young_index"]

    # Add metadata columns
    df["division"] = "01"
    df["division_name"] = "Food and non-alcoholic beverages"
    df["reference_month"] = reference_month
    df["country"] = country

    # Sort by month
    df = df.sort_values("month")

    # Select final columns for export
    df = df[
        [
            "month",
            "cpi_index",
            "cpi_index_raw",
            "n_eas",
            "total_weight",
            "is_reference",
            "division",
            "division_name",
            "reference_month",
            "country",
        ]
    ]

    # Export
    filename = f"{country.lower().replace(' ', '_')}_division_01_cpi.csv"
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)

    print(f"  Exported Division 01 CPI: {filepath}")

    return filepath


def export_ea_indices(
    ea_with_weights: pd.DataFrame,
    output_dir: str | Path,
    country: str,
    reference_month: str,
) -> Path:
    """
    Export elementary aggregate indices.

    Args:
        ea_with_weights: DataFrame with EA indices and weights
        output_dir: Output directory path
        country: Country name for filename
        reference_month: Reference month string

    Returns:
        Path to exported CSV file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare output DataFrame
    df = ea_with_weights.copy()

    # Select and rename columns
    df = df[
        [
            "month",
            "coicop_3digit",
            "category_name",
            "jevons_index",
            "jevons_index_100",
            "n_articles",
            "n_matched",
            "n_imputed",
            "weight",
            "weight_decimal",
        ]
    ].copy()

    df = df.rename(
        columns={
            "coicop_3digit": "coicop_code",
            "jevons_index_100": "ea_index",
            "category_name": "category",
        }
    )

    # Add metadata
    df["reference_month"] = reference_month
    df["country"] = country

    # Sort
    df = df.sort_values(["month", "coicop_code"])

    # Export
    filename = f"{country.lower().replace(' ', '_')}_ea_indices.csv"
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)

    print(f"  Exported EA indices: {filepath}")

    return filepath


def export_weighted_contributions(
    contributions: pd.DataFrame,
    output_dir: str | Path,
    country: str,
    reference_month: str,
) -> Path:
    """
    Export weighted contributions of each EA to the overall CPI.

    Args:
        contributions: DataFrame with weighted contributions
        output_dir: Output directory path
        country: Country name for filename
        reference_month: Reference month string

    Returns:
        Path to exported CSV file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare output
    df = contributions.copy()
    df = df.rename(
        columns={
            "coicop_3digit": "coicop_code",
            "category_name": "category",
            "jevons_index_100": "ea_index",
        }
    )

    # Add metadata
    df["reference_month"] = reference_month
    df["country"] = country

    # Sort
    df = df.sort_values(["month", "weight"], ascending=[True, False])

    # Export
    filename = f"{country.lower().replace(' ', '_')}_weighted_contributions.csv"
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)

    print(f"  Exported weighted contributions: {filepath}")

    return filepath


def export_article_details(
    article_relatives: pd.DataFrame,
    output_dir: str | Path,
    country: str,
    reference_month: str,
) -> Path:
    """
    Export article-level price relatives for detailed analysis.

    Args:
        article_relatives: DataFrame with article-level data
        output_dir: Output directory path
        country: Country name for filename
        reference_month: Reference month string

    Returns:
        Path to exported CSV file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare output
    df = article_relatives.copy()

    # Select columns
    cols = [
        "url_hash",
        "month",
        "coicop_3digit",
        "coicop_code",
        "product_name",
        "avg_price",
        "ref_price",
        "price_relative",
        "is_imputed",
        "obs_count",
    ]
    df = df[[c for c in cols if c in df.columns]]

    # Add metadata
    df["reference_month"] = reference_month
    df["country"] = country

    # Sort
    df = df.sort_values(["month", "coicop_3digit", "url_hash"])

    # Export
    filename = f"{country.lower().replace(' ', '_')}_article_details.csv"
    filepath = output_dir / filename
    df.to_csv(filepath, index=False)

    print(f"  Exported article details: {filepath}")

    return filepath


def generate_summary_report(
    young_index: pd.DataFrame,
    ea_with_weights: pd.DataFrame,
    contributions: pd.DataFrame,
    stats: dict,
    country: str,
    reference_month: str,
) -> str:
    """
    Generate a text summary report of the CPI construction.

    Args:
        young_index: Division 01 index
        ea_with_weights: EA indices with weights
        contributions: Weighted contributions
        stats: Statistics from pipeline
        country: Country name
        reference_month: Reference month

    Returns:
        Summary report as string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("CPI CONSTRUCTION SUMMARY REPORT")
    lines.append("=" * 70)
    lines.append(f"Country: {country}")
    lines.append(f"Reference Month: {reference_month}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Data summary
    lines.append("-" * 70)
    lines.append("DATA SUMMARY")
    lines.append("-" * 70)
    if "data_stats" in stats:
        ds = stats["data_stats"]
        lines.append(f"Total observations: {ds.get('valid_rows', 'N/A'):,}")
    if "ea_stats" in stats:
        es = stats["ea_stats"]
        lines.append(f"Articles in reference month: {es.get('ref_articles', 'N/A'):,}")
        lines.append(f"Imputed prices: {es.get('imputed_count', 'N/A'):,}")
        lines.append(f"Elementary aggregates: {es.get('ea_count', 'N/A')}")
    lines.append("")

    # Division 01 Index
    lines.append("-" * 70)
    lines.append("DIVISION 01 INDEX (Food and non-alcoholic beverages)")
    lines.append("-" * 70)
    lines.append(f"{'Month':<12} {'Index':>10} {'Change':>10}")
    lines.append("-" * 35)

    young_sorted = young_index.sort_values("month")
    prev_index = None
    for _, row in young_sorted.iterrows():
        # Use normalized index (which is 100 at reference month)
        idx = row["young_index_normalized"]
        if prev_index is not None:
            change = ((idx / prev_index) - 1) * 100
            change_str = f"{change:+.2f}%"
        else:
            change_str = "-"
        lines.append(f"{row['month']:<12} {idx:>10.2f} {change_str:>10}")
        prev_index = idx
    lines.append("")

    # Category breakdown (latest month)
    lines.append("-" * 70)
    lines.append("CATEGORY BREAKDOWN (Latest Month)")
    lines.append("-" * 70)
    latest_month = young_sorted["month"].iloc[-1]
    latest_contrib = contributions[contributions["month"] == latest_month].copy()
    latest_contrib = latest_contrib.sort_values("weight", ascending=False)

    lines.append(f"{'Category':<20} {'Weight':>8} {'Index':>10} {'Contrib':>10}")
    lines.append("-" * 50)
    for _, row in latest_contrib.iterrows():
        lines.append(
            f"{row['category_name'][:20]:<20} {row['weight']:>7.2f}% "
            f"{row['jevons_index_100']:>10.2f} {row['weighted_contribution']:>10.2f}"
        )
    lines.append("")

    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def export_all(
    young_index: pd.DataFrame,
    ea_with_weights: pd.DataFrame,
    contributions: pd.DataFrame,
    article_relatives: pd.DataFrame,
    stats: dict,
    output_dir: str | Path,
    country: str,
    reference_month: str,
    include_article_details: bool = False,
) -> dict:
    """
    Export all CPI outputs.

    This is the main entry point for the output module.

    Args:
        young_index: Division 01 index
        ea_with_weights: EA indices with weights
        contributions: Weighted contributions
        article_relatives: Article-level data
        stats: Pipeline statistics
        output_dir: Output directory
        country: Country name
        reference_month: Reference month
        include_article_details: If True, export article-level data

    Returns:
        Dictionary with paths to all exported files
    """
    print("\n" + "=" * 60)
    print("EXPORTING RESULTS")
    print("=" * 60)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_files = {}

    # Export main outputs
    exported_files["division_01"] = export_division_01_index(
        young_index, output_dir, country, reference_month
    )

    exported_files["ea_indices"] = export_ea_indices(
        ea_with_weights, output_dir, country, reference_month
    )

    exported_files["contributions"] = export_weighted_contributions(
        contributions, output_dir, country, reference_month
    )

    # Optionally export article details (can be large)
    if include_article_details:
        exported_files["article_details"] = export_article_details(
            article_relatives, output_dir, country, reference_month
        )

    # Generate and save summary report
    report = generate_summary_report(
        young_index,
        ea_with_weights,
        contributions,
        stats,
        country,
        reference_month,
    )

    report_path = output_dir / f"{country.lower().replace(' ', '_')}_summary_report.txt"
    with open(report_path, "w") as f:
        f.write(report)
    exported_files["summary_report"] = report_path
    print(f"  Exported summary report: {report_path}")

    print("=" * 60 + "\n")

    # Print report to console
    print(report)

    return exported_files
