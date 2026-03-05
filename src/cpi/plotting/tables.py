"""
Markdown table generation for CPI data documentation.

Generates formatted Markdown tables for the Data section of cpi_data.md,
including coverage statistics, examples, and quality metrics.
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import sys

# Handle both direct execution and module import
if __name__ == "__main__" and __package__ is None:
    # Add project root to path so 'src' module can be imported
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from src.cpi.analysis.functions import (
        load_prices_csv,
        validate_prices,
        _get_coicop_mappings,
    )
    from src.cpi.visualization.labels import (
        load_labels,
        get_country_label,
        get_source_label,
        rename_columns_with_labels,
    )
else:
    from ..analysis.functions import (
        load_prices_csv,
        validate_prices,
        _get_coicop_mappings,
    )
    from .labels import (
        load_labels,
        get_country_label,
        get_source_label,
        rename_columns_with_labels,
    )


def format_table_as_markdown(
    df: pd.DataFrame, title: str = "", description: str = ""
) -> str:
    """
    Convert DataFrame to Markdown table with optional title and description.

    Args:
        df: DataFrame to convert
        title: Optional section title
        description: Optional description text

    Returns:
        Formatted Markdown string
    """
    md = ""
    if title:
        md += f"### {title}\n\n"
    if description:
        md += f"{description}\n\n"

    # Convert DataFrame to markdown, handling empty DataFrames
    if len(df) > 0:
        # Use pandas to_markdown with proper formatting
        markdown_table = df.to_markdown(index=False)
        if markdown_table:
            md += markdown_table
        else:
            md += "*No data available*"
    else:
        md += "*No data available*"

    md += "\n\n"
    return md


def table_country_source_summary(
    df: pd.DataFrame, labels: Optional[dict] = None
) -> str:
    """
    Generate table with country, source, N_registers, N_unique_products.

    Line 5 in cpi_data.md:
    -> A table with country, source, Nregisters, Nuniqueproducts
    """
    if labels is None:
        labels = load_labels()

    if "source" not in df.columns:
        # Fallback to country only
        summary = df.groupby("country", as_index=False).agg(
            N_registers=("url_hash", "size"),
            N_unique_products=("url_hash", "nunique"),
        )
    else:
        summary = df.groupby(["country", "source"], as_index=False).agg(
            N_registers=("url_hash", "size"),
            N_unique_products=("url_hash", "nunique"),
        )

    # Apply country labels
    summary["country"] = summary["country"].apply(
        lambda x: get_country_label(x, labels)
    )

    # Apply source labels if present
    if "source" in summary.columns:
        summary["source"] = summary["source"].apply(
            lambda x: get_source_label(x, labels)
        )

    summary = summary.sort_values(["country", "N_registers"], ascending=[True, False])

    # Rename columns with labels
    summary = rename_columns_with_labels(summary, labels)

    return format_table_as_markdown(
        summary,
        title="Data Coverage by Country and Source",
        description="Number of price observations (registers) and unique products per country and data source.",
    )


def table_wayback_coverage(df: pd.DataFrame, labels: Optional[dict] = None) -> str:
    """
    Generate table with country, source, date_scraping_initiated,
    N_items_with_wayback_data, N_months_of_data_considering_wayback.

    Line 9 in cpi_data.md:
    -> A table with country, source, date_Scraping_initiated, Nitems_with_wayback_data,
       N_months_of_data_considering_wayback
    """
    if labels is None:
        labels = load_labels()

    if "source" not in df.columns:
        group_cols = ["country"]
    else:
        group_cols = ["country", "source"]

    records = []
    for keys, group_df in df.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)

        # Date scraping initiated (earliest date with wayback==0, i.e., live data)
        live_data = group_df[~group_df["is_wayback"]]
        date_initiated = (
            live_data["date_parsed"].min().date() if len(live_data) > 0 else None
        )

        # Items with wayback data
        items_with_wayback = group_df[group_df["is_wayback"]]["url_hash"].nunique()

        # Total months of data (considering wayback)
        n_months = group_df["month"].nunique()

        record = dict(zip(group_cols, keys))
        record.update(
            {
                "date_scraping_initiated": str(date_initiated)
                if date_initiated
                else "N/A",
                "N_items_with_wayback_data": items_with_wayback,
                "N_months_of_data_considering_wayback": n_months,
            }
        )
        records.append(record)

    summary = pd.DataFrame(records)

    # Apply country labels
    summary["country"] = summary["country"].apply(
        lambda x: get_country_label(x, labels)
    )

    # Apply source labels if present
    if "source" in summary.columns:
        summary["source"] = summary["source"].apply(
            lambda x: get_source_label(x, labels)
        )

    summary = summary.sort_values(["country"], ascending=[True])

    # Rename columns with labels
    summary = rename_columns_with_labels(summary, labels)

    return format_table_as_markdown(
        summary,
        title="Wayback Machine Coverage",
        description="Historical data coverage through Internet Archive's Wayback Machine, showing when scraping started and temporal depth.",
    )


def table_unit_value_example(
    df: pd.DataFrame, n_examples: int = 5, labels: Optional[dict] = None
) -> str:
    """
    Generate example table showing unit value standardization process.

    Line 13 in cpi_data.md:
    -> Example of unit value standardization with a small table, showing price,
       amount parsing, unit parsing, unit value calculation, and final unit value.
    """
    if labels is None:
        labels = load_labels()

    # Essential columns that must be present and non-null
    essential_cols = ["product_name", "amount", "units", "unit_value"]
    available_essential = [col for col in essential_cols if col in df.columns]

    if len(available_essential) < 3:
        return format_table_as_markdown(
            pd.DataFrame(),
            title="Unit Value Standardization Examples",
            description="*Insufficient columns available for unit value examples*",
        )

    # Filter to rows with non-null values in essential columns (price is optional)
    example_df = df[df[available_essential].notna().all(axis=1)].copy()

    if len(example_df) == 0:
        return format_table_as_markdown(
            pd.DataFrame(),
            title="Unit Value Standardization Examples",
            description="*No complete examples available*",
        )

    # Sample a few examples
    example_df = example_df.sample(n=min(n_examples, len(example_df)), random_state=42)

    # Capitalize all words in product names
    example_df["product_name"] = example_df["product_name"].str.title()

    # Select and order columns (price is optional)
    output_cols = [
        col
        for col in ["product_name", "price", "amount", "units", "unit_value"]
        if col in example_df.columns
    ]
    example_df = example_df[output_cols]

    # Round numeric columns for readability
    if "price" in example_df.columns:
        example_df["price"] = pd.to_numeric(example_df["price"], errors="coerce").round(
            2
        )
    if "unit_value" in example_df.columns:
        example_df["unit_value"] = pd.to_numeric(
            example_df["unit_value"], errors="coerce"
        ).round(4)

    # Rename columns with labels
    example_df = rename_columns_with_labels(example_df, labels)

    return format_table_as_markdown(
        example_df,
        title="Unit Value Standardization Examples",
        description="Examples showing how raw prices are converted to standardized unit values for comparability.",
    )


def table_coicop_classification_example(
    df: pd.DataFrame, n_examples: int = 5, labels: Optional[dict] = None
) -> str:
    """
    Generate example table showing COICOP classification.

    Line 17 in cpi_data.md:
    -> Example of COICOP classification with a small table, showing product name,
       retailer category, COICOP category (with code), and COICOP subcategory (with code).
    """
    if labels is None:
        labels = load_labels()

    required_cols = ["product_name", "coicop_code"]
    if not all(col in df.columns for col in required_cols):
        return format_table_as_markdown(
            pd.DataFrame(),
            title="COICOP Classification Examples",
            description="*Insufficient columns available for COICOP examples*",
        )

    # Filter to rows with complete COICOP data
    example_df = df[df[required_cols].notna().all(axis=1)].copy()

    if len(example_df) == 0:
        return format_table_as_markdown(
            pd.DataFrame(),
            title="COICOP Classification Examples",
            description="*No complete examples available*",
        )

    # Sample examples
    example_df = example_df.sample(n=min(n_examples, len(example_df)), random_state=42)

    # Capitalize all words in product names
    example_df["product_name"] = example_df["product_name"].str.title()

    # Build output columns
    output_cols = ["product_name"]

    # Get COICOP mappings for proper titles
    coicop_mappings = _get_coicop_mappings()

    # Add COICOP level 1 code and title
    if "coicop_1digit" in example_df.columns:
        output_cols.append("coicop_1digit")
        # Create COICOP Level 1 title column using Level 1 mappings
        if 1 in coicop_mappings:
            example_df["coicop_1digit_title"] = example_df["coicop_1digit"].map(
                coicop_mappings[1]
            )
            output_cols.append("coicop_1digit_title")

    # Add COICOP level 4 code and title
    output_cols.append("coicop_code")
    # Use Level 4 mappings for Level 4 titles
    if 4 in coicop_mappings:
        example_df["coicop_4digit_title"] = example_df["coicop_code"].map(
            coicop_mappings[4]
        )
        output_cols.append("coicop_4digit_title")

    # Filter to available columns
    output_cols = [col for col in output_cols if col in example_df.columns]
    example_df = example_df[output_cols]

    # Rename columns with labels
    example_df = rename_columns_with_labels(example_df, labels)

    return format_table_as_markdown(
        example_df,
        title="COICOP Classification Examples",
        description="Examples of product classification using the COICOP (Classification of Individual Consumption by Purpose) framework.",
    )


def table_coicop_l1_by_country(df: pd.DataFrame, labels: Optional[dict] = None) -> str:
    """
    Generate pivot table with COICOP Level 1 in rows and countries in columns.

    Line 19 in cpi_data.md:
    -> A table with country in the columns and COICOP Level 1 in the rows,
       showing the number of products per source and per COICOP Level 1,
       with the Total products of each row in the first column.
    """
    if labels is None:
        labels = load_labels()

    # Get COICOP mappings for proper titles
    coicop_mappings = _get_coicop_mappings()

    # Count unique products by country and COICOP L1
    # Aggregate across sources if present
    pivot_data = (
        df.groupby(["coicop_1digit", "country"])["url_hash"].nunique().reset_index()
    )
    pivot_data.columns = ["coicop_1digit", "country", "n_items"]

    # Create pivot table with countries as columns
    pivot = (
        pivot_data.pivot(index="coicop_1digit", columns="country", values="n_items")
        .fillna(0)
        .astype(int)
    )

    # Add total column at the beginning
    pivot.insert(0, "Total", pivot.sum(axis=1))

    # Reset index to make COICOP code a regular column
    pivot = pivot.reset_index()
    pivot.columns.name = None

    # Add COICOP Level 1 code and title as separate columns
    pivot = pivot.rename(columns={"coicop_1digit": "coicop_1digit_code"})
    if 1 in coicop_mappings:
        pivot["coicop_1digit_title"] = pivot["coicop_1digit_code"].map(
            coicop_mappings[1]
        )

    # Reorder columns: Total, Code, Title, then countries
    country_cols = [
        col
        for col in pivot.columns
        if col not in ["Total", "coicop_1digit_code", "coicop_1digit_title"]
    ]
    pivot = pivot[["Total", "coicop_1digit_code", "coicop_1digit_title"] + country_cols]

    # Rename the COICOP columns
    pivot = pivot.rename(
        columns={
            "coicop_1digit_code": "COICOP Code (Level 1)",
            "coicop_1digit_title": "COICOP Title (Level 1)",
        }
    )

    # Apply country labels to column headers (skip "Total" and "COICOP Level 1" columns)
    country_cols = [
        col for col in pivot.columns if col not in ["COICOP Level 1", "Total"]
    ]
    for col in country_cols:
        pivot = pivot.rename(columns={col: get_country_label(col, labels)})

    # Sort by total descending
    pivot = pivot.sort_values("Total", ascending=False).reset_index(drop=True)

    return format_table_as_markdown(
        pivot,
        title="Product Coverage by COICOP Level 1 and Country",
        description="Number of unique products per consumption category (COICOP Level 1) across countries.",
    )


def generate_markdown_tables(input_path: str) -> str:
    """
    Generate all Markdown tables for the Data section of cpi_data.md.

    Args:
        input_path: Path to the input CSV file

    Returns:
        Complete Markdown string with all tables
    """
    # Load and validate data
    df = load_prices_csv(input_path)
    df_valid, _ = validate_prices(df)

    # Load labels once for all tables
    labels = load_labels()

    # Generate all tables
    markdown = "# Data Tables\n\n"
    markdown += "*Auto-generated tables for the Data section*\n\n"
    markdown += "---\n\n"

    markdown += table_country_source_summary(df_valid, labels=labels)
    markdown += table_wayback_coverage(df_valid, labels=labels)
    markdown += table_unit_value_example(df_valid, n_examples=5, labels=labels)
    markdown += table_coicop_classification_example(
        df_valid, n_examples=5, labels=labels
    )
    markdown += table_coicop_l1_by_country(df_valid, labels=labels)

    return markdown


def print_markdown_tables(input_path: str):
    """
    Generate and print all Markdown tables to stdout.

    Args:
        input_path: Path to the input CSV file
    """
    markdown = generate_markdown_tables(input_path)
    print(markdown)


def main():
    """Main entry point for standalone execution."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate Markdown tables from CPI price data."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/cpi/analysis/all_countries_supermarket_prices.csv",
        help="Path to input CSV file (default: data/cpi/analysis/all_countries_supermarket_prices.csv)",
    )
    args = parser.parse_args()

    try:
        print_markdown_tables(args.input)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
