import re
from pathlib import Path
from typing import List
import pandas as pd
import requests


def download_coicop_excel(output_dir: Path) -> Path:
    """
    Download COICOP 2018 Excel file from UN Stats if not already present.

    Args:
        output_dir: Directory to save the Excel file

    Returns:
        Path to the Excel file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / "coicop_categories.xlsx"

    if excel_path.exists():
        print(f"Excel file already exists at {excel_path}")
        return excel_path

    url = "https://unstats.un.org/unsd/classifications/Econ/Download/COICOP_2018_English_structure.xlsx"
    print(f"Downloading COICOP Excel from {url}...")

    response = requests.get(url)
    response.raise_for_status()

    with open(excel_path, "wb") as f:
        f.write(response.content)

    print(f"Downloaded to {excel_path}")
    return excel_path


def parse_keywords_list(keywords_str: str) -> List[str]:
    """
    Parse keywords string into a list of items.

    Splits by lines starting with "*" and removes any parenthetical content
    like (01.2.4.5).

    Args:
        keywords_str: String containing keywords with bullet points

    Returns:
        List of cleaned keyword items
    """
    if not isinstance(keywords_str, str) or not keywords_str.strip():
        return []

    # Clean up encoding artifacts like _x000D_ (carriage returns) and non-breaking spaces
    keywords_str = re.sub(r"_x000D_", "", keywords_str)
    keywords_str = keywords_str.replace("\xa0", " ")  # Replace non-breaking spaces

    # Split by lines starting with "*" or by newlines followed by "*"
    # Handle both "\n*" and just "*" patterns
    items = re.split(r"[\n\r]+\s*\*\s*|\*\s+", keywords_str.strip())

    # Remove leading "*" from first item if present
    if items and items[0].startswith("*"):
        items[0] = items[0][1:].strip()

    # Clean each item: remove parenthetical content like (01.2.4.5)
    cleaned_items = []
    for item in items:
        item = item.strip()
        if item:
            # Remove parenthetical content with code patterns like (01.2.4.5)
            cleaned = re.sub(r"\s*\([0-9.]+\)\s*", "", item).strip()
            # Clean up extra whitespace
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                cleaned_items.append(cleaned)

    return cleaned_items


def load_and_process_coicop(excel_path: Path, digit_level: int = 4) -> pd.DataFrame:
    """
    Load Excel file and process COICOP data.

    Filters for rows with exactly digit_level dots in the code column,
    combines includes and alsoIncludes into keywords,
    parses keywords into lists, and creates an "all_info" column
    combining title, includes, and alsoIncludes for embedding/matching.

    Args:
        excel_path: Path to the COICOP Excel file
        digit_level: Number of dots in COICOP code (digit level)

    Returns:
        Processed DataFrame with columns: code, title, includes, alsoIncludes,
        excludes, keywords_list, all_info
    """
    print(f"Loading Excel file from {excel_path}...")
    df = pd.read_excel(excel_path)

    print(f"Total rows in Excel: {len(df)}")

    # Filter for rows with exactly digit_level - 1 dots in the code column
    n_dots = digit_level - 1
    df = df[df["code"].astype(str).str.count(r"\.") == n_dots].copy()
    print(f"Rows with {digit_level}-digit level codes: {len(df)}")

    # Select required columns and rename to standard names
    required_cols = ["code", "intro", "title", "includes", "alsoIncludes", "excludes"]
    df = df[required_cols].copy()

    # Rename to standard column names used throughout the workflow
    df = df.rename(columns={"code": "coicop_code", "title": "coicop_title"})

    # Create "keywords" column combining intro, includes, and alsoIncludes
    # This is used for embedding and fuzzy matching
    def clean_keywords(text):
        """Clean keywords by removing _x000D_ and converting bullets to semicolons."""
        if not text or pd.isna(text):
            return ""

        text = str(text).strip()

        # Remove _x000D_ encoding
        text = text.replace("_x000D_", ", ")

        # Replace bullet points (* followed by space) with semicolon separator
        # Handle both "* item" and newline + "* item" patterns
        text = text.replace("\n* ", ", ")
        text = text.replace("* ", ", ")

        # Clean up multiple spaces
        text = " ".join(text.split())

        # Remove leading/trailing semicolons and spaces
        text = text.strip(", ").strip()

        text = text.replace(", , ", ", ")
        text = text.replace(".,", ".")

        return text

    df["keywords"] = df.apply(
        lambda row: ", ".join(
            filter(
                None,
                [
                    clean_keywords(row["intro"]) if pd.notna(row["intro"]) else "",
                    (
                        clean_keywords(row["includes"])
                        if pd.notna(row["includes"])
                        else ""
                    ),
                    (
                        clean_keywords(row["alsoIncludes"])
                        if pd.notna(row["alsoIncludes"])
                        else ""
                    ),
                ],
            )
        ),
        axis=1,
    )

    return df


def get_coicop_categories(data_dir: Path = None, digit_level: int = 4) -> pd.DataFrame:
    """
    Main function to download (if needed) and process COICOP categories.

    Args:
        data_dir: Directory where coicop_categories.xlsx is stored.
                 Defaults to data/prices/_enrich relative to project root.
        digit_level: Number of dots in COICOP code (digit level). Defaults to 4.

    Returns:
        Processed DataFrame with COICOP categories
    """
    if data_dir is None:
        # Find project root and construct path
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent
        data_dir = project_root / "data" / "prices" / "_enrich"

    # Download Excel if not present
    excel_path = download_coicop_excel(data_dir)

    # Load and process
    df = load_and_process_coicop(excel_path, digit_level=digit_level)

    return df


if __name__ == "__main__":
    # Example usage
    df = get_coicop_categories()
    print("\nProcessed COICOP Categories:")
    print(df.head(10))
    print(f"\nTotal processed rows: {len(df)}")
    print("\nSample keywords_list:")
    for idx, row in df.head(3).iterrows():
        print(f"\nCode: {row['coicop_code']}")
        print(f"Title: {row['coicop_title']}")
        print(f"Keywords list: {row['keywords_list']}")
    df.to_csv("coicop_categories.csv", index=False)
    df_no_services = df[~df["coicop_code"].str.endswith(" (S)")]
    df_no_services.to_csv("coicop_categories_no_services.csv", index=False)
