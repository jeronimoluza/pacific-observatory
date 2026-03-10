"""
Gemini API client utilities for COICOP classification.

This module provides utilities for interacting with Google's Gemini API
for product classification tasks.
"""

import os
import csv
from typing import List, Dict

import pandas as pd


def _is_incomplete_trailing_csv_row(line: str) -> bool:
    """Return True when a trailing CSV row appears truncated."""
    stripped_line = line.rstrip()
    if not stripped_line:
        return False

    if stripped_line.count('"') % 2 == 1:
        return True

    try:
        row_data = next(csv.reader([line], strict=True))
    except csv.Error:
        return True

    return len(row_data) < 2


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
    # Create COICOP context string
    coicop_lines = []
    for _, row in coicop_context.iterrows():
        code = row["coicop_code"]
        title = row["coicop_title"]
        keywords = row.get("keywords", "")
        coicop_lines.append(f"{code} | {title} | {keywords}")

    coicop_context_str = "\n".join(coicop_lines)

    # Create products list
    products_str = "\n".join([f'"{p}"' for p in batch_products])

    prompt = f"""You are a product classification expert. Your task is to classify products into COICOP (Classification of Individual Consumption According to Purpose) categories.

COICOP Categories (code | title | keywords):
{coicop_context_str}

Products to classify:
{products_str}

Instructions:
1. For each product, identify the most appropriate COICOP code based on the product name and category
2. Use the keywords to help match products to categories
3. Return ONLY a CSV with three columns: product_w_cat, coicop_code, confidence
4. The confidence should be a number between 0 and 1 indicating how confident you are in the classification
5. Do not include any explanations, just the CSV data
6. Make sure to include ALL products in your response

Output format (CSV):
product_w_cat,coicop_code,confidence
"product name; category",01.1.1.0.1,0.95
"""

    return prompt


def parse_gemini_response(response_text: str) -> List[Dict[str, str]]:
    """
    Parse CSV response from Gemini.

    Args:
        response_text: Raw response text from Gemini (should be CSV format)

    Returns:
        List of dictionaries with product_w_cat, coicop_code, confidence
    """
    results = []

    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("csv"):
            response_text = response_text[3:]

    response_text = response_text.strip()

    # Handle truncated responses by removing only actually incomplete last rows
    lines = response_text.split("\n")
    if lines and _is_incomplete_trailing_csv_row(lines[-1]):
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
                # Parse confidence (default to None if not present or invalid)
                confidence = None
                if len(row_data) >= 3 and row_data[2]:
                    try:
                        conf_val = float(row_data[2].strip())
                        # Validate confidence is between 0 and 1
                        if 0 <= conf_val <= 1:
                            confidence = conf_val
                    except (ValueError, TypeError):
                        pass

                # Only add if we have both required fields and haven't seen this product before
                if product_w_cat and code and product_w_cat not in seen:
                    seen.add(product_w_cat)
                    results.append(
                        {
                            "product_w_cat": product_w_cat,
                            "coicop_code": code,
                            "confidence": confidence,
                        }
                    )
        except Exception:
            # Skip lines that can't be parsed
            pass

    return results
