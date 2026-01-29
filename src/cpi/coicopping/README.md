# COICOP Classification Workflow

## Overview

This module implements a complete pipeline for classifying supermarket products into COICOP (Classification of Individual Consumption According to Purpose) categories and extracting standardized unit prices. The workflow processes:

1. **Scrapy scraped data**: Weekly collection of current supermarket product data
2. **Wayback Machine data**: Historical product data from archived URLs

Both data sources are assumed to be available (see `src/cpi/price_scraping` for scraping pipeline).

The pipeline then:
- Cleans and normalizes product names and quantities
- Extracts quantities using **multi-candidate extraction** (captures ALL quantity expressions)
- Classifies product **usability** into tiered statuses (resolved, contradictory, promotional)
- Detects **promotional/bundle products** for exclusion
- Calculates **standardized unit prices** (price per kg, liter, or meter)
- Classifies products into COICOP categories using **Google Gemini AI**
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
│ (cleaning.py, data_preparation.py)                              │
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
│ STEP 3: EXTRACT QUANTITIES (Standardized Unit Price System)     │
│ (quantity/ subpackage)                                          │
├─────────────────────────────────────────────────────────────────┤
│ - Multi-candidate extraction: capture ALL quantity expressions  │
│ - Detect promotions: "buy 2 get 1", "bonus", "family pack"      │
│ - Classify usability: resolved/contradictory/promotional        │
│ - Assign extraction tier: Tier 1 (weight/volume), 2 (count), 3  │
│ - Calculate standardized unit_value: price per kg/L/mt          │
│ Output: amount, units, unit_value, usability_status,            │
│         extraction_tier, has_promotion, n_candidates             │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: CLASSIFY WITH COICOP                                    │
│ (classification.py)                                             │
├─────────────────────────────────────────────────────────────────┤
│ 4a. Download COICOP categories (4-digit level)                  │
│ 4b. Group by url_hash, keep latest product_w_cat               │
│ 4c. Classify unclassified products with Gemini AI               │
│     - Batch processing (600 products per batch)                 │
│     - Uses Gemini 2.0 Flash (or 3.0 Flash Preview)              │
│     - Maps product_w_cat → coicop_code & coicop_title           │
│     - Includes confidence scores                                │
│ 4d. Incremental classification (only new url_hash entries)      │
│ Output: url_hash, product_w_cat, coicop_code, coicop_title,     │
│         confidence                                              │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: MERGE & FINALIZE                                        │
│ (quantity/extraction.py - merge_quantities_with_gemini)         │
├─────────────────────────────────────────────────────────────────┤
│ - Merge quantities with COICOP classifications                  │
│ - Add date column (scraped_at or wayback_timestamp)             │
│ - Sort by url_hash and date                                     │
│ - Include all standardized unit price columns                   │
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
| `product_name_original` | string | Original product name before any cleaning | Input |
| `product_name` | string | Cleaned product name (lowercase, no accents) | Cleaned |
| `product_w_cat` | string | Product name with category: "{product_only}; {category}" | Cleaned |
| `price` | float | Original product price | Input |
| `currency` | string | Currency code (FJ, USD, AUD, etc.) | Input |
| `amount` | string | Extracted quantity value (e.g., "250 ml", "1 kg") | Extracted |
| `units` | string | Extracted unit count (e.g., "6 pack", "1") | Extracted |
| `unit_value` | float | Price per standard unit (kg, liter, or mt) | Calculated |
| `usability_status` | string | Classification status (resolved_mass/volume/length/count_food, contradictory, promotion_or_bundle, pending_review) | Classified |
| `extraction_tier` | int | Tier 1 (weight/volume), Tier 2 (count), Tier 3 (per-item), or None (excluded) | Classified |
| `standard_unit` | string | Standard unit for unit_value (kg, L, mt, or count) | Derived |
| `n_candidates` | int | Number of quantity candidates found | Extracted |
| `has_promotion` | bool | True if promotional keywords detected | Detected |
| `rejection_reason` | string | Reason for rejection if contradictory | Classified |
| `pending_review` | bool | True if flagged for manual review | Classified |
| `coicop_code` | string | 4-digit COICOP classification code (e.g., "01.1.8.9") | Classified |
| `coicop_title` | string | COICOP category title (e.g., "Chocolate confectionery") | Classified |
| `confidence` | float | Classification confidence score (0-1) | Classified |
| `source` | string | Data source (spider name: mh_online, aldi_au, etc.) | Input |
| `country` | string | Country code (fiji, samoa, vanuatu, etc.) | Input |
| `product_url` | string | Original product URL | Input |
| `date` | datetime | Timestamp (YYYY-MM-DD HH:MM:SS format) | Derived |
| `product_id` | string | Original product ID from source | Input |
| `wayback` | int | 1 if from Wayback Machine, 0 if not | Derived |

**Notes:**
- **One row per product per date**: Each unique url_hash appears multiple times (once per scrape date)
- **Time series**: Sorted by url_hash and date to track price evolution
- **Unclassified products**: Have `coicop_code` and `coicop_title` as NaN if classification failed
- **Usability statuses**:
  - `resolved_mass`: Weight-based products (kg, g, lb, oz)
  - `resolved_volume`: Volume-based products (L, ml, gal)
  - `resolved_length`: Length-based products (m, cm, ft)
  - `resolved_count_food`: Count-based food products (eggs, apples, etc.)
  - `contradictory`: Multiple conflicting quantities found
  - `promotion_or_bundle`: Promotional/bundle products (excluded from unit price)
  - `pending_review`: Flagged for manual review (included provisionally)
- **Extraction tiers**:
  - Tier 1: Weight/volume measurements (highest priority)
  - Tier 2: Count-based measurements
  - Tier 3: Per-item fallback (no quantity detected)
  - None: Excluded products (promotions, contradictory)
- **Date derivation**:
  - Scrapy items: Use `scraped_at` timestamp
  - Wayback items: Convert `wayback_timestamp` (YYYYMMDDHHMMSS) to YYYY-MM-DD HH:MM:SS

## Processing Steps

### 1. Load Data (`loading.py`)

Loads all scrapy and wayback items from the price scraping directory structure.

```bash
python -c "from src.cpi.coicopping.loading import load_price_scraping_data; df = load_price_scraping_data(); print(f'Loaded {len(df)} items')"
```

### 2. Clean & Prepare (`data_preparation.py`)

Cleans product names and creates product-category combinations for classification.

**Key functions:**
- `clean_product_names()`: Remove hardcoded strings from config/string_cleaning.json
- `remove_amounts_and_quantities()`: Remove "250ml", "6 pack", etc.
- `clean_product_only()`: Remove parentheses, normalize accents
- `clean_category()`: Lowercase, remove "Home" prefix
- `create_product_with_category()`: Combine product and category
- `clean_product_w_cat()`: Remove numbers, single chars, stopwords
- `prepare_coicop_matching_data()`: Main orchestration function

**Output columns:**
- `product_name_original`: Original product name before cleaning
- `product_name`: Cleaned product name
- `product_only`: Product name without quantities
- `product_w_cat`: Product + category for classification

### 3. Extract Quantities (`quantity/` subpackage)

Extracts quantities using a **multi-candidate extraction system** with usability classification.

**Submodules:**
- `extraction.py`: Main extraction orchestration
- `candidates.py`: Multi-candidate extraction (captures ALL quantity expressions)
- `usability.py`: Classifies products into usability statuses
- `promotion.py`: Detects promotional/bundle products
- `conversions.py`: Unit conversion factors
- `regex.py`: Regex patterns for quantity extraction

**Extraction logic:**
1. **Multi-candidate extraction**: Capture ALL quantity expressions in product name
2. **Promotion detection**: Flag "buy 2 get 1", "bonus", "family pack", etc.
3. **Usability classification**: Classify into resolved/contradictory/promotional statuses
4. **Tier assignment**: Tier 1 (weight/volume), Tier 2 (count), Tier 3 (per-item)
5. **Unit value calculation**: Standardized price per kg, liter, or meter

**Special cases:**
- If "per kg" pattern found: amount = "1 kg", units = None
- If "per each" pattern found: amount = None, units = "1"
- If promotional keywords found: flagged as `promotion_or_bundle`
- If multiple conflicting quantities: flagged as `contradictory`

**Output columns:**
- `amount`: Extracted quantity value (e.g., "250 ml")
- `units`: Extracted unit count (e.g., "6 pack")
- `unit_value`: Price per standard unit (kg, L, mt)
- `usability_status`: Classification status
- `extraction_tier`: Tier 1/2/3 or None
- `standard_unit`: Standard unit for unit_value
- `n_candidates`: Number of quantity candidates found
- `has_promotion`: Boolean flag for promotional products
- `rejection_reason`: Reason if contradictory
- `pending_review`: Boolean flag for manual review

### 4. Classify with COICOP (`classification.py`)

Uses Google Generative AI (Gemini 2.0/3.0 Flash) to classify products into COICOP categories.

**Workflow:**
1. Download COICOP 2018 categories (4-digit level) from UN Stats (`coicop_categories.py`)
2. Load existing classifications from `gemini_classification.csv` (if present)
3. Create `products_input.csv` with unique url_hash and product_w_cat
4. Identify new/unclassified products (url_hash not in gemini_classification.csv)
5. Batch classify new products with Gemini (600 products per batch)
6. Append new classifications to `gemini_classification.csv` immediately after each batch
7. Merge all classifications back to original data

**Incremental Classification:**
- Only classifies url_hash entries not already in `gemini_classification.csv`
- Appends new classifications to existing file after each batch
- If `gemini_classification.csv` doesn't exist, all url_hash are classified
- Avoids redundant API calls for previously classified products
- Handles API quota limits gracefully (stops and saves progress)

**Classification:**
- Uses Gemini 2.0 Flash or 3.0 Flash Preview model
- Maps `product_w_cat` → `coicop_code` (e.g., "01.1.8.9")
- Retrieves `coicop_title` from COICOP reference
- Includes confidence scores (0-1)
- Marks unclassified items as NaN

**Output columns:**
- `coicop_code`: 4-digit COICOP code
- `coicop_title`: COICOP category title
- `confidence`: Classification confidence score

### 5. Merge & Finalize (`quantity/extraction.py`)

Merges quantities with COICOP classifications and prepares final output.

**Final steps:**
- Merge quantities DataFrame with gemini_classification.csv
- Include all standardized unit price columns
- Sort by url_hash and date
- Save to `data/cpi/analysis/all_countries_supermarket_prices.csv`

**Function:** `merge_quantities_with_gemini(df_quantities, gemini_classification_path)`

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

### Final Steps: Reclassify Unclassified Products

After the initial classification run, some products may remain unclassified (marked as NaN in `coicop_code` and `coicop_title`). This can happen when product descriptions are unclear or ambiguous.

**Re-run Classification:**

Use the `--reclassify-missing` flag to attempt classification of previously unclassified products:

```bash
poetry run python src/cpi/coicopping/main.py --reclassify-missing
```

**What it does:**
- Identifies products with missing COICOP classifications (NaN values)
- Attempts to classify them using Gemini AI
- Updates `gemini_classification.csv` with new classifications
- Can be run multiple times as the Gemini API allows

**Important Notes:**
- Some products may never be classified if their descriptions are too vague or unclear
- Each run consumes Gemini API quota
- Products with unclear descriptions should be reviewed manually if needed
- The final output will still include unclassified products for manual review

**After Reclassification:**

Once you've run `main.py --reclassify-missing`, re-run the main workflow to regenerate the final output with updated classifications:

```bash
poetry run python src/cpi/coicopping/main.py
```

This will merge the newly classified products with the quantity data and update `data/cpi/analysis/all_countries_supermarket_prices.csv` with the latest classifications.

## Module Structure

```
src/cpi/coicopping/
├── __init__.py
├── main.py                    # Main orchestration script
├── loading.py                 # Load scrapy and wayback data
├── cleaning.py                # Clean product names
├── data_preparation.py        # Prepare data for classification
├── classification.py          # COICOP classification with Gemini
├── coicop_categories.py       # Download and process COICOP categories
├── gemini_client.py           # Gemini API client utilities
├── utils.py                   # Shared utilities
├── config/                    # Configuration files
│   ├── string_cleaning.json   # Source-specific cleaning rules
│   └── promotion_keywords.json # Promotion detection keywords
└── quantity/                  # Quantity extraction subpackage
    ├── __init__.py            # Public API exports
    ├── extraction.py          # Main extraction orchestration
    ├── candidates.py          # Multi-candidate extraction
    ├── usability.py           # Usability classification
    ├── promotion.py           # Promotion detection
    ├── conversions.py         # Unit conversion factors
    └── regex.py               # Regex patterns for extraction
```

## Configuration Files

### `config/string_cleaning.json`
Source-specific strings to remove from product names:
```json
{
  "aldi_au": ["string1", "string2"],
  "samoa_market": ["stringA", "stringB"]
}
```

### `config/promotion_keywords.json`
Global and source-specific promotional keywords:
```json
{
  "global": ["bonus", "buy 2 get 1", "family pack"],
  "source_specific": {
    "samoa_market": ["combo", "bundle"]
  }
}
```

### `quantity/regex.py`
Defines regex patterns for quantity extraction:
- `AMOUNT_REGEX`: Weight/volume patterns (g, kg, ml, l, etc.)
- `UNITS_REGEX`: Count patterns (pack, can, piece, etc.)
- `X_SEPARATOR_REGEX`: Patterns with "x" separator (e.g., "28 x 6pack")
- `PER_KG_REGEX`: Per kilogram patterns
- `PER_EACH_REGEX`: Per each patterns
- `COUNT_UNITS`: List of count unit types
- `AMOUNT_UNITS`: List of amount unit types
- `STOPWORDS`: Stopwords for text cleaning

### `quantity/conversions.py`
Defines conversion factors for standardizing units:
- `WEIGHT_TO_KG`: Weight conversions to kg
- `VOLUME_TO_LT`: Volume conversions to liters
- `LENGTH_TO_MT`: Length conversions to meters
- `UNIT_CONVERSIONS`: Combined conversion dictionary

## Intermediate Files

Generated during processing:

| File | Location | Purpose |
|------|----------|---------|
| `coicop_categories.xlsx` | `data/cpi/coicopping/` | Downloaded COICOP Excel from UN Stats |
| `coicop_categories.csv` | `data/cpi/coicopping/` | All COICOP categories (4-digit) |
| `coicop_categories_no_services.csv` | `data/cpi/coicopping/` | COICOP categories excluding services |
| `products_input.csv` | `data/cpi/coicopping/` | Unique products to classify (url_hash, product_w_cat) |
| `gemini_classification.csv` | `data/cpi/coicopping/` | Classification results (url_hash, product_w_cat, coicop_code, coicop_title, confidence) |

## Error Handling

### Unclassified Products
If a product fails to classify with Gemini:
- `coicop_code`, `coicop_title`, and `confidence` are marked as NaN
- Product is included in final output for manual review
- Can be reclassified using `--reclassify-missing` flag

### Quantity Extraction Issues
- **Multiple conflicting quantities**: Flagged as `contradictory`, excluded from unit price
- **Promotional products**: Flagged as `promotion_or_bundle`, excluded from unit price
- **No quantity detected**: Assigned Tier 3 (per-item), unit_value based on price
- **Missing category**: Product name used alone for classification
- **Missing price**: unit_value cannot be calculated (NaN)

### API Quota Limits
- Gemini classification stops gracefully when quota exceeded
- Progress saved after each batch (600 products)
- Can resume from where it left off in next run

## Dependencies

- `pandas`: Data manipulation
- `google-generativeai`: Gemini API for classification
- `requests`: Download COICOP Excel from UN Stats
- `openpyxl`: Read Excel files
- `nltk`: Stopwords for text cleaning

## Environment Variables

**Required for COICOP classification:**
```bash
export GOOGLE_API_KEY='your-api-key-here'
```

Get your API key from: https://aistudio.google.com/apikey

## Standardized Unit Price System

The quantity extraction system implements a **multi-candidate extraction** approach with usability classification to produce standardized unit prices.

### Key Features

1. **Multi-Candidate Extraction**
   - Captures ALL quantity expressions in a product name
   - Example: "maltesers fun size share pack chocolate 11 pack 132g"
     - Candidate 1: "11 pack"
     - Candidate 2: "132g"
   - Stores `n_candidates` to track extraction complexity

2. **Usability Classification**
   - **resolved_mass**: Weight-based (kg, g, lb, oz) → unit_value per kg
   - **resolved_volume**: Volume-based (L, ml, gal) → unit_value per liter
   - **resolved_length**: Length-based (m, cm, ft) → unit_value per meter
   - **resolved_count_food**: Count-based food items (eggs, apples) → unit_value per count
   - **contradictory**: Multiple conflicting quantities → excluded
   - **promotion_or_bundle**: Promotional keywords detected → excluded
   - **pending_review**: Flagged for manual review → included provisionally

3. **Extraction Tiers**
   - **Tier 1**: Weight/volume measurements (highest priority for CPI)
   - **Tier 2**: Count-based measurements (food items only)
   - **Tier 3**: Per-item fallback (no quantity detected)
   - **None**: Excluded products (promotions, contradictory)

4. **Promotion Detection**
   - Global keywords: "bonus", "buy 2 get 1", "family pack", "value pack"
   - Source-specific keywords from `config/promotion_keywords.json`
   - False positive filtering: "free range", "gluten free", etc.

5. **Standardized Unit Values**
   - All prices converted to price per standard unit
   - Weight → price per kg
   - Volume → price per liter
   - Length → price per meter
   - Count (food) → price per count

### Success Metrics

From the main.py output, the system reports:
- **Total resolved**: Percentage of products with usable unit prices
- **Food products resolved**: Target >= 30% for food items (COICOP 01.x.x.x)
- **Usability status distribution**: Breakdown by classification status
- **Extraction tier distribution**: Breakdown by tier assignment

### Example Output

```
STANDARDIZED UNIT PRICE METRICS
────────────────────────────────────────
Usability Status Distribution:
  resolved_mass: 15234 (45.2%)
  resolved_volume: 8456 (25.1%)
  resolved_count_food: 3421 (10.2%)
  contradictory: 2134 (6.3%)
  promotion_or_bundle: 1876 (5.6%)
  pending_review: 2543 (7.6%)

  TOTAL RESOLVED: 27111 (80.5%)
  Food products resolved: 8234/12456 (66.1%)
  ✓ PRD Target Met: >= 30% food products resolved

Promotional products detected: 1876

Extraction Tier Statistics:
  Tier 1 (Weight/Volume): 23690 (70.3%)
  Tier 2 (Count): 3421 (10.2%)
  Tier 3 (Per-item): 2543 (7.6%)
  Excluded (no tier): 4010 (11.9%)
```

## Next Steps

After generating `all_countries_supermarket_prices.csv`:
1. Use for **price analysis** (trend analysis, inflation tracking)
2. Generate **Consumer Price Index (CPI)** by COICOP category
3. Track **price evolution** over time by product
4. Identify **price anomalies** and outliers
5. Filter by **usability_status** to include only resolved products
6. Use **extraction_tier** to prioritize high-quality measurements

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
