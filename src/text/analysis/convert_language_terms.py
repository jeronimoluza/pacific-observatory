"""
Convert language_terms.csv to topics_words.json format.

This script reads EPU terms from the CSV file and merges them with existing
English terms in topics_words.json, creating a multi-language term dictionary.

Usage:
    python src/text/analysis/convert_language_terms.py
"""

import csv
import json
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
CSV_PATH = ANALYSIS_DIR / "language_terms.csv"
JSON_PATH = ANALYSIS_DIR / "topics_words.json"

# Mapping from CSV language names to config codes
LANGUAGE_MAPPING = {
    "Chinese (Simplified)": "chinese_simplified",
    "Chinese (Traditional)": "chinese_traditional",
    "Japanese": "japanese",
    "Korean": "korean",
    "Thai": "thai",
    "Vietnamese": "vietnamese",
    "Indonesian": "indo",
    "Malay": "malay",
    "Khmer": "km",
    "Lao": "lao",
    "Mongolian": "mn",
    "Tamil": "tamil",
    "French": "fr",
    "Filipino/Tagalog": "filipino",
    "Hindi": "hindi",
    "Māori": "maori",
    "Samoan": "samoan",
    "Tongan": "tongan",
    "Tok Pisin": "tok_pisin",
    "Bislama": "bislama",
    "Solomon Islands Pijin": "solomon_islands_pijin",
    "Palauan": "palauan",
    "Marshallese": "marshallese",
    "iTaukei (Fijian)": "fijian",
}

# Mapping from CSV category names to JSON keys
CATEGORY_MAPPING = {
    "Economic": "economic",
    "Policy": "policy",
    "Uncertainty": "uncertainty",
}


def parse_terms(term_string: str) -> list[str]:
    """
    Parse a term string that may contain multiple terms separated by '|'.

    Example: "IMF | Quỹ Tiền tệ Quốc tế" -> ["IMF", "Quỹ Tiền tệ Quốc tế"]
    """
    if not term_string or term_string.strip() == "":
        return []

    terms = []
    for term in term_string.split("|"):
        term = term.strip()
        # Skip placeholder terms like "(loan)" or empty terms
        if term and not term.startswith("(") and not term.endswith("(loan)"):
            # Clean up terms that have "(loan)" suffix
            if " (loan)" in term:
                term = term.replace(" (loan)", "").strip()
            if term:
                terms.append(term)

    return terms


def load_existing_json() -> dict:
    """Load existing topics_words.json file."""
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv_terms() -> dict:
    """
    Load and parse terms from CSV file.

    Returns a dict structure: {language_code: {category: [terms]}}
    """
    language_terms = {}

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            csv_language = row.get("Language", "").strip()
            csv_category = row.get("Category", "").strip()
            translation = row.get("Translation / search tokens (local)", "").strip()

            # Skip if language or category not recognized
            if csv_language not in LANGUAGE_MAPPING:
                continue
            if csv_category not in CATEGORY_MAPPING:
                continue

            lang_code = LANGUAGE_MAPPING[csv_language]
            category = CATEGORY_MAPPING[csv_category]

            # Initialize language structure if needed
            if lang_code not in language_terms:
                language_terms[lang_code] = {
                    "economic": [],
                    "policy": [],
                    "uncertainty": [],
                }

            # Parse and add terms
            terms = parse_terms(translation)
            for term in terms:
                if term not in language_terms[lang_code][category]:
                    language_terms[lang_code][category].append(term)

    return language_terms


def merge_and_save(existing: dict, new_terms: dict) -> dict:
    """
    Merge new language terms with existing JSON structure.
    Preserves English terms and additional_terms.
    """
    # Start with English terms
    merged = {"en": existing.get("en", {})}

    # Add all new language terms
    for lang_code, categories in sorted(new_terms.items()):
        merged[lang_code] = categories

    # Save to JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    return merged


def main():
    print(f"Loading existing JSON from {JSON_PATH}")
    existing = load_existing_json()

    print(f"Loading CSV terms from {CSV_PATH}")
    new_terms = load_csv_terms()

    print(f"Found {len(new_terms)} languages in CSV")
    for lang_code in sorted(new_terms.keys()):
        terms = new_terms[lang_code]
        total = sum(len(t) for t in terms.values())
        print(f"  - {lang_code}: {total} terms")

    print("\nMerging and saving to JSON...")
    merged = merge_and_save(existing, new_terms)

    print(f"\nFinal structure has {len(merged)} language entries:")
    for lang_code in merged.keys():
        if lang_code == "en":
            print(f"  - {lang_code}: (preserved with additional_terms)")
        else:
            terms = merged[lang_code]
            total = sum(len(t) for t in terms.values())
            print(f"  - {lang_code}: {total} terms")

    print(f"\nSaved to {JSON_PATH}")


if __name__ == "__main__":
    main()
