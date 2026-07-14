"""
LEGACY — retired Gemini-2.0-Flash COICOP classifier. Not part of the current
`prices` pipeline (`run.py prices process`); superseded by the structural
extraction + (embedding → head) classifier in `src/prices/enrich/`. Kept for
reference only. Its output `gemini_classification.csv` is a stale artifact — do
not treat it as current.

COICOP classification package for price scraping data.

This package provides tools for:
- Loading and preparing price scraping data
- Extracting quantities from product names
- Classifying products with COICOP codes using Gemini AI
- Merging and finalizing data for analysis
"""

__version__ = "0.1.0"
