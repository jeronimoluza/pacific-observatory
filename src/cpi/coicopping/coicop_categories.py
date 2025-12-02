import re
from pathlib import Path
from typing import List, Dict, Any
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
    keywords_str = re.sub(r'_x000D_', '', keywords_str)
    keywords_str = keywords_str.replace('\xa0', ' ')  # Replace non-breaking spaces
    
    # Split by lines starting with "*" or by newlines followed by "*"
    # Handle both "\n*" and just "*" patterns
    items = re.split(r'[\n\r]+\s*\*\s*|\*\s+', keywords_str.strip())
    
    # Remove leading "*" from first item if present
    if items and items[0].startswith('*'):
        items[0] = items[0][1:].strip()
    
    # Clean each item: remove parenthetical content like (01.2.4.5)
    cleaned_items = []
    for item in items:
        item = item.strip()
        if item:
            # Remove parenthetical content with code patterns like (01.2.4.5)
            cleaned = re.sub(r'\s*\([0-9.]+\)\s*', '', item).strip()
            # Clean up extra whitespace
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            if cleaned:
                cleaned_items.append(cleaned)
    
    return cleaned_items


def load_and_process_coicop(excel_path: Path) -> pd.DataFrame:
    """
    Load Excel file and process COICOP data.
    
    Filters for rows with exactly 3 dots in the code column,
    combines includes and alsoIncludes into keywords,
    and parses keywords into lists.
    
    Args:
        excel_path: Path to the COICOP Excel file
        
    Returns:
        Processed DataFrame
    """
    print(f"Loading Excel file from {excel_path}...")
    df = pd.read_excel(excel_path)
    
    print(f"Total rows in Excel: {len(df)}")
    
    # Filter for rows with exactly 3 dots in the code column
    df = df[df['code'].astype(str).str.count(r'\.') == 3].copy()
    print(f"Rows with exactly 3 dots in code: {len(df)}")
    
    # Select required columns
    required_cols = ['code', 'title', 'includes', 'alsoIncludes', 'excludes']
    df = df[required_cols].copy()
    
    # Combine includes and alsoIncludes into keywords
    df['keywords'] = df.apply(
        lambda row: (
            (str(row['includes']).strip() if pd.notna(row['includes']) else '') + 
            ' ' + 
            (str(row['alsoIncludes']).strip() if pd.notna(row['alsoIncludes']) else '')
        ).strip(),
        axis=1
    )
    
    # Parse keywords into lists and clean
    df['keywords_list'] = df['keywords'].apply(parse_keywords_list)
    
    # Drop the intermediate keywords column if not needed
    df = df.drop(columns=['keywords'])
    
    return df


def get_coicop_categories(data_dir: Path = None) -> pd.DataFrame:
    """
    Main function to download (if needed) and process COICOP categories.
    
    Args:
        data_dir: Directory where coicop_categories.xlsx is stored.
                 Defaults to data/cpi/coicopping relative to project root.
        
    Returns:
        Processed DataFrame with COICOP categories
    """
    if data_dir is None:
        # Find project root and construct path
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent
        data_dir = project_root / "data" / "cpi" / "coicopping"
    
    # Download Excel if not present
    excel_path = download_coicop_excel(data_dir)
    
    # Load and process
    df = load_and_process_coicop(excel_path)
    
    return df


if __name__ == "__main__":
    # Example usage
    df = get_coicop_categories()
    print("\nProcessed COICOP Categories:")
    print(df.head(10))
    print(f"\nTotal processed rows: {len(df)}")
    print("\nSample keywords_list:")
    for idx, row in df.head(3).iterrows():
        print(f"\nCode: {row['code']}")
        print(f"Title: {row['title']}")
        print(f"Keywords list: {row['keywords_list']}")
