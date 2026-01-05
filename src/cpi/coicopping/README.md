# COICOP Classification Workflow

## Overview

This module implements a complete pipeline for classifying supermarket products into COICOP (Classification of Individual Consumption According to Purpose) categories. The workflow processes:

1. **Scrapy scraped data**: Weekly collection of current supermarket product data
2. **Wayback Machine data**: Historical product data from archived URLs

Both data sources are assumed to be available (see `src/cpi/price_scraping` for scraping pipeline).

The pipeline then:
- Cleans and normalizes product names and quantities
- Extracts amount, units, and calculates unit values
- Classifies products into COICOP categories using Google Generative AI (Gemini)
- Produces final time-series product data for CPI analysis

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT DATA                                                      │
├─────────────────────────────────────────────────────────────────┤
│ Scrapy Items (JSONL)          │ Wayback Items (JSON)            │
│ - product_name                │ - product_name                  │
│ - price                       │ - price                         │
│ - currency                    │ - currency                      │
│ - category                    │ - category (optional)           │
│ - url                         │ - wayback_url                   │
│ - scraped_at (timestamp)      │ - wayback_timestamp             │
│ - url_hash (MD5)              │ - url_hash (MD5)                │
│ - product_id                  │ - product_id                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: LOAD & MERGE DATA                                       │
│ (loading.py)                                                    │
├─────────────────────────────────────────────────────────────────┤
│ - Load all JSONL files from data/cpi/price_scraping/            │
│ - Combine scrapy and wayback data                               │
│ - Add metadata: country, source, filename                       │
│ - Add date column (scraped_at or wayback_timestamp)             │
│ Output: Combined DataFrame with all items                       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: CLEAN & PREPARE DATA                                    │
│ (cleaning.py, prestep.py)                                       │
├─────────────────────────────────────────────────────────────────┤
│ - Remove parentheses/brackets from product names                │
│ - Remove accents (é → e, ñ → n)                                 │
│ - Extract product_only (remove quantities: "250ml", "6 pack")   │
│ - Clean category names (lowercase, remove "Home" prefix)        │
│ - Create product_w_cat: "{product_only}; {category}"            │
│ Output: Cleaned product names and categories                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: EXTRACT QUANTITIES                                      │
│ (extract_quantities.py)                                         │
├─────────────────────────────────────────────────────────────────┤
│ - Extract amount (weight/volume): 250ml, 1kg, etc.              │
│ - Extract units (count): 6 pack, 12 cans, etc.                  │
│ - Calculate unit_value: price per kg/liter/mt                   │
│ Output: amount, units, unit_value columns                       │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: CLASSIFY WITH COICOP                                    │
│ (coicop_matching.py)                                            │
├─────────────────────────────────────────────────────────────────┤
│ 4a. Download COICOP categories (4-digit level)                  │
│ 4b. Group by url_hash, keep latest product_w_cat               │
│ 4c. Classify unclassified products with Gemini AI               │
│     - Batch processing (600 products per batch)                 │
│     - Maps product_w_cat → coicop_code & coicop_title           │
│ 4d. Mark unclassified items (if classification fails)           │
│ Output: url_hash, product_w_cat, coicop_code, coicop_title      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: MERGE & FINALIZE                                        │
│ (extract_quantities.py - merge_quantities_with_gemini)          │
├─────────────────────────────────────────────────────────────────┤
│ - Merge quantities with COICOP classifications                  │
│ - Add date column (scraped_at or wayback_timestamp)             │
│ - Sort by url_hash and date                                     │
│ Output: Final time-series product data                          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ FINAL OUTPUT                                                    │
│ data/cpi/analysis/all_countries_supermarket_prices.csv          │
├─────────────────────────────────────────────────────────────────┤
│ One row per product per date (time series)                      │
│ Sorted by: url_hash, date                                       │
│ Ready for: Price analysis, CPI calculation                      │
└─────────────────────────────────────────────────────────────────┘
```

## Input Data Formats

### Scrapy Items (JSONL)
Located in: `data/cpi/price_scraping/{country}/{source}/raw_items/{source}_YYYYMMDD_HHMMSS.jsonl`

```json
{
  "product_id": "6710000390",
  "product_name": "POTATOES TABLE 60/80 KG",
  "price": "1.40",
  "category": "Home > Fruits & Vegetables > Imported Vegetables",
  "url": "https://mh.com.fj/product/potatoes-table-60-80-kg/",
  "scraped_at": "Wed, 05 Nov 2025 13:09:00 GMT",
  "url_hash": "cd2add3dac0ec9e87033dd906a22a196",
  "currency": "FJ"
}
```

### Wayback Items (JSON)
Located in: `data/cpi/price_scraping/{country}/{source}/wayback_machine_data/items/{url_hash}.json`

```json
[
  {
    "wayback_url": "https://web.archive.org/web/20210924153110/https://www.mh.com.fj/product/punjas-chillie-powder-50g/",
    "wayback_timestamp": "20210924153110",
    "url_hash": "0b58b1c78532e2477dfcab7bc3378f69",
    "scraped_at": "2025-12-22T13:11:02.570624",
    "product_name": "PUNJAS CHILLIE POWDER 50G",
    "price": "$1.50",
    "product_id": "5831001050"
  }
]
```

## Output Schema

### Final Output: `all_countries_supermarket_prices.csv`

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `url_hash` | string | MD5 hash of product URL (unique identifier) | Input |
| `product_name` | string | Cleaned product name (lowercase, no accents) | Cleaned |
| `product_w_cat` | string | Product name with category: "{product_only}; {category}" | Cleaned |
| `price` | float | Original product price | Input |
| `currency` | string | Currency code (FJ, USD, AUD, etc.) | Input |
| `amount` | float | Extracted quantity value (e.g., 250 for "250ml") | Extracted |
| `units` | string | Extracted unit type (e.g., "ml", "pack", "1" for no unit) | Extracted |
| `unit_value` | float | Price per standard unit (kg, liter, or mt) | Calculated |
| `coicop_code` | string | 4-digit COICOP classification code (e.g., "01.1.8.9") | Classified |
| `coicop_title` | string | COICOP category title (e.g., "Chocolate confectionery") | Classified |
| `source` | string | Data source (spider name: mh_online, aldi_au, etc.) | Input |
| `country` | string | Country code (fiji, samoa, vanuatu, etc.) | Input |
| `product_url` | string | Original product URL | Input |
| `date` | string | Timestamp (YYYY-MM-DD HH:MM:SS format) | Derived |
| `product_id` | string | Original product ID from source | Input |
| `wayback` | int | 1 if from Wayback Machine, 0 if not | Derived |

**Notes:**
- **One row per product per date**: Each unique url_hash appears multiple times (once per scrape date)
- **Time series**: Sorted by url_hash and date to track price evolution
- **Unclassified products**: Have `coicop_code` and `coicop_title` as NaN if classification failed
- **Date derivation**:
  - Scrapy items: Use `scraped_at` timestamp
  - Wayback items: Convert `wayback_timestamp` (YYYYMMDDHHMMSS) to YYYY-MM-DD HH:MM:SS

## Processing Steps

### 1. Load Data (`loading.py`)

Loads all scrapy and wayback items from the price scraping directory structure.

```bash
python -c "from src.cpi.coicopping.loading import load_price_scraping_data; df = load_price_scraping_data(); print(f'Loaded {len(df)} items')"
```

### 2. Clean & Prepare (`prestep.py`)

Cleans product names and creates product-category combinations for classification.

**Key functions:**
- `clean_product_names()`: Remove hardcoded strings from string_cleaning.json
- `remove_amounts_and_quantities()`: Remove "250ml", "6 pack", etc.
- `clean_product_only()`: Remove parentheses, normalize accents
- `clean_category()`: Lowercase, remove "Home" prefix
- `create_product_with_category()`: Combine product and category
- `clean_product_w_cat()`: Remove numbers, single chars, stopwords

**Output columns:**
- `product_name`: Cleaned product name
- `product_only`: Product name without quantities
- `product_w_cat`: Product + category for classification

### 3. Extract Quantities (`extract_quantities.py`)

Extracts amount, units, and calculates unit values using regex patterns.

**Extraction logic:**
- **Amount**: Weight/volume (g, kg, ml, l, etc.)
- **Units**: Count (pack, can, piece, etc.)
- **Unit value**: Calculated as `price / (amount * count)` converted to standard unit (kg, liter, mt)

**Special cases:**
- If "per kg" pattern found: amount = "1 kg", units = NaN
- If "per each" pattern found: amount = NaN, units = "1"
- If no quantity found: amount = NaN, units = "1" (default)

**Output columns:**
- `amount`: Extracted quantity value
- `units`: Extracted unit type
- `unit_value`: Price per standard unit

### 4. Classify with COICOP (`coicop_matching.py`)

Uses Google Generative AI (Gemini) to classify products into COICOP categories.

**Workflow:**
1. Download COICOP 2018 categories (4-digit level) from UN Stats
2. Load existing classifications from `gemini_classification.csv` (if present)
3. Group by url_hash, keep latest product_w_cat
4. Identify new/unclassified products (url_hash not in gemini_classification.csv)
5. Batch classify new products with Gemini (600 products per batch)
6. Append new classifications to `gemini_classification.csv`
7. Merge all classifications back to original data

**Incremental Classification:**
- Only classifies url_hash entries not already in `gemini_classification.csv`
- Appends new classifications to existing file
- If `gemini_classification.csv` doesn't exist, all url_hash are classified
- Avoids redundant API calls for previously classified products

**Classification:**
- Maps `product_w_cat` → `coicop_code` (e.g., "01.1.8.9")
- Retrieves `coicop_title` from COICOP reference
- Marks unclassified items as NaN

**Output columns:**
- `coicop_code`: 4-digit COICOP code
- `coicop_title`: COICOP category title

### 5. Merge & Finalize (`extract_quantities.py`)

Merges quantities with COICOP classifications and prepares final output.

**Final steps:**
- Merge quantities DataFrame with gemini_classification.csv
- Sort by url_hash and date
- Save to `data/cpi/analysis/all_countries_supermarket_prices.csv`

## Usage

### Run Complete Workflow

The main orchestration script runs all steps automatically:

```bash
cd /path/to/pacific-observatory
poetry run python src/cpi/coicopping/main.py
```

**What it does:**
1. Loads all price scraping data (scrapy JSONL + wayback JSON)
2. Cleans and prepares product names
3. Extracts quantities (amount, units, unit_value)
4. Classifies products with COICOP using Gemini AI
5. Merges classifications with quantity data
6. Saves final output to `data/cpi/analysis/all_countries_supermarket_prices.csv`

**Options:**

```bash
# Skip classification step (use existing gemini_classification.csv)
poetry run python src/cpi/coicopping/main.py --skip-classification

# Run with debug logging
poetry run python src/cpi/coicopping/main.py --log-level DEBUG

# Get help
poetry run python src/cpi/coicopping/main.py --help
```

### Run Individual Steps

**Step 1: Load Data**
```bash
python -c "from src.cpi.coicopping.loading import load_price_scraping_data; df = load_price_scraping_data(); print(f'Loaded {len(df)} items')"
```

**Step 2: Clean & Prepare**
```bash
python -c "from src.cpi.coicopping.prestep import prepare_coicop_matching_data; df = prepare_coicop_matching_data(); print(f'Prepared {len(df)} products')"
```

**Step 3: Extract Quantities**
```bash
python -c "from src.cpi.coicopping.extract_quantities import extract_quantities; df = extract_quantities(); print(f'Extracted {len(df)} products')"
```

**Step 4: COICOP Classification**
```bash
python -c "from src.cpi.coicopping.coicop_matching import run_coicop_matching; run_coicop_matching()"
```

**Step 5: Merge & Finalize**
```bash
python src/cpi/coicopping/extract_quantities.py
```

## Configuration Files

### `regex_config.py`
Defines regex patterns for quantity extraction:
- `AMOUNT_REGEX`: Weight/volume patterns
- `UNITS_REGEX`: Count patterns
- `X_SEPARATOR_REGEX`: Patterns with "x" separator (e.g., "28 x 6pack")
- `PER_KG_REGEX`: Per kilogram patterns
- `PER_EACH_REGEX`: Per each patterns

### `unit_conversions.py`
Defines conversion factors for standardizing units to kg, liter, or mt.

## Intermediate Files

Generated during processing:

| File | Location | Purpose |
|------|----------|---------|
| `coicop_categories.csv` | `data/cpi/coicopping/` | All COICOP categories (4-digit) |
| `coicop_categories_no_services.csv` | `data/cpi/coicopping/` | COICOP categories excluding services |
| `products_input.csv` | `data/cpi/coicopping/` | Unique products to classify |
| `gemini_classification.csv` | `data/cpi/coicopping/` | Classification results (url_hash, product_w_cat, code, title) |
| `unit_values_w_categories.csv` | `data/cpi/coicopping/` | Merged quantities with COICOP (intermediate) |

## Error Handling

### Unclassified Products
If a product fails to classify with Gemini:
- `coicop_code` and `coicop_title` are marked as NaN
- Product is included in final output for manual review
- Can be reclassified in future runs

### Missing Data
- **Missing amount/units**: Default to units = "1"
- **Missing category**: Product name used alone for classification
- **Missing price**: unit_value cannot be calculated (NaN)

## Dependencies

- `pandas`: Data manipulation
- `google-generativeai`: Gemini API for classification
- `requests`: Download COICOP Excel from UN Stats

## Environment Variables

**Required for COICOP classification:**
```bash
export GOOGLE_API_KEY='your-api-key-here'
```

Get your API key from: https://aistudio.google.com/apikey

## Next Steps

After generating `all_countries_supermarket_prices.csv`:
1. Use for **price analysis** (trend analysis, inflation tracking)
2. Generate **Consumer Price Index (CPI)** by COICOP category
3. Track **price evolution** over time by product
4. Identify **price anomalies** and outliers

## Changelog

### Product Name & Category Consistency (Latest)

**Modification**: Enhanced `load_price_scraping_data()` in `loading.py` to ensure product name and category consistency across scrapy and wayback data.

**What Changed**:
- Groups scrapy items by `url_hash` and retrieves the **last (latest) occurrence** for both `product_name` and `category`
- Creates two mapping dictionaries: `product_name_mapping` and `category_mapping`
- Applies these mappings to all wayback machine data, replacing their `product_name` and `category` with the latest scrapy values

**Rationale**:
- **Prevents quantity extraction disruptions**: Product names and categories can change over time in scrapy data. By using the latest values consistently across all wayback historical data, we ensure that quantity extraction logic doesn't encounter conflicting product identities for the same URL
- **Maintains time-series integrity**: When analyzing price evolution through wayback data, the product identity must remain stable. This change ensures `url_hash` always maps to a single, consistent product name and category across all time periods
- **Improves unit value price tracking**: Since product names/categories are now constant for each `url_hash`, the extraction of quantity changes (amount, units, unit_value) won't be confused by product metadata variations, allowing accurate tracking of price per unit over time

**Implementation Details**:
- Uses vectorized pandas operations with boolean masks for efficiency
- Only overwrites wayback data where scrapy data exists; gracefully handles missing data
- Logs mapping creation and application for transparency

## References

- **COICOP 2018**: https://unstats.un.org/unsd/classifications/Econ/Download/
- **Google Generative AI**: https://ai.google.dev/
- **Wayback Machine API**: https://archive.org/help/wayback_api.php
- **Price Scraping Pipeline**: See `src/cpi/price_scraping` for Scrapy and Wayback scraping implementation
