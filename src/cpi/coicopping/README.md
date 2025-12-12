# COICOP Matching with Gemini 2.0 Flash

This module provides an end-to-end workflow for classifying products into COICOP (Classification of Individual Consumption According to Purpose) categories using Google's Gemini 2.0 Flash model.

## Workflow Overview

The `coicop_matching.py` script orchestrates a 4-step process:

1. **Download & Process COICOP Data**: Downloads the COICOP 2018 Excel file from UN Stats and saves processed CSVs
2. **Prepare Product Input**: Creates `products_input.csv` from price scraping data with `url_hash` and `product_w_cat` columns
3. **Classify with Gemini**: Uses Gemini 2.0 Flash to classify products in batches of 2000
4. **Generate Final Output**: Creates `gemini_classification.csv` with classification results

## Output Files

All output files are saved to `data/cpi/coicopping/`:

- **coicop_categories.csv** - Full COICOP categories (code, title, keywords, etc.)
- **coicop_categories_no_services.csv** - COICOP categories excluding services (ending with ' (S)')
- **products_input.csv** - Unique products with url_hash and product_w_cat
- **gemini_classification.csv** - Final classifications with columns:
  - `url_hash` - Hash of product URL
  - `product_w_cat` - Product name with category
  - `code` - COICOP code (e.g., "01.1.8.9")
  - `title` - COICOP category title

## Setup Requirements

### 1. Install Google Generative AI Library

```bash
pip install google-generativeai
```

Or add to your project dependencies:

```bash
poetry add google-generativeai
```

### 2. Get Google API Key

1. Visit: https://aistudio.google.com/apikey
2. Create a new API key
3. Copy the key

### 3. Set Environment Variable

**macOS/Linux:**

```bash
# Option 1: Set for current session
export GOOGLE_API_KEY='your-api-key-here'

# Option 2: Set permanently in shell profile
echo "export GOOGLE_API_KEY='your-api-key-here'" >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell):**

```powershell
$env:GOOGLE_API_KEY='your-api-key-here'
```

**Or pass directly when running:**

```bash
GOOGLE_API_KEY='your-api-key-here' python src/cpi/coicopping/coicop_matching.py
```

## Usage

### Basic Usage

From the project root directory:

```bash
python src/cpi/coicopping/coicop_matching.py
```

### With API Key

```bash
GOOGLE_API_KEY='your-api-key-here' python src/cpi/coicopping/coicop_matching.py
```

### Programmatic Usage

```python
from src.cpi.coicopping.coicop_matching import run_coicop_matching
from pathlib import Path

# Run with default project root
run_coicop_matching()

# Or specify custom project root
project_root = Path('/path/to/project')
run_coicop_matching(project_root)
```

## Workflow Details

### Step 1: Download and Process COICOP Data

- Downloads COICOP 2018 Excel from UN Stats (if not already present)
- Processes to digit level 4 (e.g., "01.1.8.9")
- Saves full categories and categories without services
- Creates "keywords" column combining intro, includes, and alsoIncludes

### Step 2: Create Products Input

- Loads price scraping data using `prepare_coicop_matching_data()`
- Extracts `url_hash` and `product_w_cat` columns
- Deduplicates by product_w_cat (keeps first occurrence)
- Saves to `products_input.csv`

### Step 3: Classify with Gemini

- Loads COICOP categories without services as context
- Processes products in batches of 2000
- For each batch:
  - Formats prompt with COICOP reference and product list
  - Calls Gemini 2.0 Flash API
  - Parses CSV response with code and title
- Handles API errors gracefully (continues with next batch)

### Step 4: Generate Final Output

- Merges product input with classification results
- Deduplicates by url_hash and product_w_cat
- Saves final output with all required columns
- Prints summary statistics

## Prompt Format

The prompt sent to Gemini follows this structure:

```
Using LLM mode (no creating any Python script), classify each product from the products list according to the COICOP categories.

COICOP CATEGORIES REFERENCE:
Code | Title | Keywords
...

PRODUCTS TO CLASSIFY:
1. product_w_cat_1
2. product_w_cat_2
...

For each product, determine the most appropriate COICOP code and title based on the keywords and descriptions.

Output ONLY a CSV format with these columns: product_w_cat, code, title
Do NOT include any other text, explanations, or markdown formatting.
```

## Expected Output Format

The Gemini response is expected to be CSV format:

```csv
product_w_cat,code,title
"half meter tube; pantry confectionery","01.1.8.9","Other sugar confectionery and desserts n.e.c. (ND)"
"product name","code","category title"
```

## Error Handling

The script includes robust error handling:

- **Missing API Key**: Provides detailed setup instructions
- **Missing google-generativeai**: Instructs to install the library
- **API Failures**: Logs error and continues with next batch
- **CSV Parsing Errors**: Logs warning with response preview
- **Missing Columns**: Validates required columns and lists available ones

## Performance Notes

- **Batch Size**: 2000 products per batch (configurable)
- **API Calls**: One call per batch
- **Processing Time**: Depends on number of products and API response time
- **Cost**: Uses Gemini 2.0 Flash (check Google's pricing)

## Troubleshooting

### "GOOGLE_API_KEY environment variable not set"

Set the environment variable as described in Setup section.

### "google-generativeai library not installed"

Install with: `pip install google-generativeai`

### "No products were successfully classified"

Check:
- API key is valid
- Internet connection is working
- Gemini API is accessible
- Check console output for specific batch errors

### CSV Parsing Errors

The script logs warnings if Gemini's response doesn't parse correctly. Check:
- Gemini is returning CSV format
- No markdown code blocks in response
- Column names match: product_w_cat, code, title

## Data Flow Diagram

```
coicop_categories.xlsx (UN Stats)
    ↓
download_coicop_excel()
    ↓
load_and_process_coicop()
    ↓
coicop_categories.csv + coicop_categories_no_services.csv
    ↓
prepare_coicop_matching_data() [from price scraping data]
    ↓
products_input.csv (url_hash, product_w_cat)
    ↓
classify_products_with_gemini() [batches of 2000]
    ↓
Gemini 2.0 Flash API
    ↓
parse_gemini_response()
    ↓
generate_final_output()
    ↓
gemini_classification.csv (url_hash, product_w_cat, code, title)
```

## Functions Reference

### Main Entry Point

- `run_coicop_matching(project_root=None)` - Orchestrates the complete workflow

### Step Functions

- `download_and_save_coicop_data(project_root=None)` - Steps 1
- `create_products_input_csv(project_root=None)` - Step 2
- `classify_products_with_gemini(products_input_df, coicop_no_services_df, project_root=None, batch_size=2000)` - Step 3
- `generate_final_output(products_input_df, classification_results_df, project_root=None)` - Step 4

### Utility Functions

- `setup_google_api_key()` - Validates and returns API key
- `format_gemini_prompt(batch_products, coicop_context)` - Creates prompt
- `parse_gemini_response(response_text)` - Parses CSV response
- `get_project_root(current_file=None)` - Gets project root directory

## Dependencies

- `pandas` - Data manipulation
- `google-generativeai` - Gemini API access
- Standard library: `os`, `sys`, `json`, `csv`, `io`, `pathlib`, `typing`

## Notes

- The script reuses existing COICOP Excel file if already downloaded
- Products are deduplicated by product_w_cat (keeps first occurrence)
- Final output is deduplicated by url_hash and product_w_cat
- All file paths are relative to project root
- Batch processing allows handling large product datasets
- API errors in one batch don't stop the entire workflow
