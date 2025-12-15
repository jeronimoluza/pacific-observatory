# Wayback Machine Scraping

This document describes the wayback machine scraping feature that allows you to extract historical product data from archived versions of product URLs.

## Overview

The wayback machine scraper:
1. Loads all items scraped by a spider
2. Deduplicates items by URL hash
3. Fetches available snapshots from the Wayback Machine for each URL
4. Extracts product data from each snapshot using the spider's CSS selectors
5. Saves the historical data to JSON files organized by URL hash

## Usage

### Basic Command

```bash
poetry run python src/cpi/price_scraping/run_spider.py <spider_name> --scrape-wayback --from <date>
```

### Examples

#### Scrape wayback data for rbpatel up to 2025-01-01

```bash
poetry run python src/cpi/price_scraping/run_spider.py rbpatel --scrape-wayback --from 2025-01-01
```

#### Scrape wayback data for all spiders up to 2024-12-31

```bash
poetry run python src/cpi/price_scraping/run_spider.py --all --scrape-wayback --from 2024-12-31
```

## Arguments

- `<spider_name>`: Name of the spider (e.g., `rbpatel`, `mh_online`, `aldi_au`, etc.)
- `--all`: Run wayback scraping for all spiders (optional, mutually exclusive with spider name)
- `--scrape-wayback`: Enable wayback machine scraping (required)
- `--from <date>`: End timestamp for wayback snapshots in YYYY-MM-DD format (required)
- `--output-dir`: Output directory for data (default: `data/cpi/price_scraping`)

## Output Structure

Wayback data is saved in the following directory structure:

```
data/cpi/price_scraping/
├── <country>/
│   └── <spider_name>/
│       └── wayback_machine_data/
│           ├── <url_hash_1>.json
│           ├── <url_hash_2>.json
│           └── ...
```

### Example Output File

File: `data/cpi/price_scraping/fiji/rbpatel/wayback_machine_data/1bfd98e4c65e7a85ba3bad2f5b89d195.json`

```json
[
  {
    "product_name": "Victory Laundry Green Soap 800g",
    "price": "$4.65",
    "category": "Detergent/Cleaners/Household",
    "product_id": "V6048",
    "wayback_url": "https://web.archive.org/web/20221204212345/https://rbpatel.com.fj/product/victory-laundry-green-soap-800g/",
    "wayback_timestamp": "20221204212345",
    "url_hash": "1bfd98e4c65e7a85ba3bad2f5b89d195",
    "scraped_at": "2025-12-15T13:36:29.833175"
  },
  {
    "product_name": "Victory Laundry Green Soap 800g",
    "price": "$5.75",
    "category": "Detergent/Cleaners/Household",
    "product_id": "V6048",
    "wayback_url": "https://web.archive.org/web/20230331091239/https://rbpatel.com.fj/product/victory-laundry-green-soap-800g/",
    "wayback_timestamp": "20230331091239",
    "url_hash": "1bfd98e4c65e7a85ba3bad2f5b89d195",
    "scraped_at": "2025-12-15T13:36:31.170493"
  }
]
```

## Output Fields

Each snapshot object contains:

- **wayback_url**: Full URL to the Wayback Machine archive
- **wayback_timestamp**: Timestamp of the snapshot (YYYYMMDDHHMMSS format)
- **url_hash**: MD5 hash of the original product URL
- **scraped_at**: ISO timestamp when the wayback scraping was performed
- **Extracted fields**: All fields extracted using the spider's CSS selectors (e.g., `product_name`, `price`, `category`, `product_id`)

## How It Works

### 1. CSS Selector Configuration

Each spider defines CSS selectors in `src/cpi/price_scraping/price_scraping/selectors.py`:

```python
SPIDER_SELECTORS = {
    "rbpatel": {
        "product_name": ["main#main div.product-main h1::text"],
        "price": ["div.product-main span[class='woocommerce-Price-amount amount'] bdi::text"],
        "category": ["div.product-main span.posted_in a::text"],
        "product_id": ["span[class='sku']::text"],
    },
    # ... other spiders
}
```

### 2. Wayback Machine API

The scraper uses `waybackpy` to query the Wayback Machine CDX API:

```python
cdx = WaybackMachineCDXServerAPI(
    url,
    user_agent=user_agent,
    end_timestamp=from_date  # YYYY-MM-DD format
)
snapshots = cdx.snapshots()  # Returns list of available snapshots
```

### 3. Data Extraction

For each snapshot:
1. Fetch the HTML content from the Wayback Machine archive URL
2. Parse the HTML with BeautifulSoup
3. Apply CSS selectors to extract product data
4. Handle both `::text` pseudo-elements and `::attr()` attributes

### 4. Deduplication

Items are deduplicated by URL hash (MD5 of the original URL) before processing. This ensures each unique product URL is only processed once, even if it appears multiple times in the scraped data.

## Implementation Details

### Files Modified

1. **src/cpi/price_scraping/price_scraping/selectors.py** (NEW)
   - Centralized CSS selectors for all spiders
   - `get_selectors(spider_name)` function to retrieve selectors

2. **src/cpi/price_scraping/price_scraping/wayback_scraper.py** (NEW)
   - `WaybackScraper` class for handling wayback machine scraping
   - Methods for fetching snapshots, extracting data, and saving results

3. **src/cpi/price_scraping/run_spider.py** (MODIFIED)
   - Added `--scrape-wayback` and `--from` CLI arguments
   - Added `run_wayback_scraping()` function
   - Added `load_scraped_items()` function to load JSONL data
   - Added `get_spider_country()` function for directory structure

4. **All spider files** (MODIFIED)
   - Updated to use centralized selectors from `selectors.py`
   - Changed from inline `SELECTORS` dict to `get_selectors(spider_name)`

## Error Handling

The scraper handles various error conditions:

- **No snapshots found**: Logs warning and skips URL
- **Failed to fetch snapshot**: Logs debug message and continues to next snapshot
- **Extraction errors**: Logs debug message and continues with partial data
- **Missing items directory**: Logs warning and exits gracefully
- **Invalid JSON**: Logs error and skips invalid lines

## Performance Considerations

- **Deduplication**: Reduces API calls by processing each unique URL only once
- **Progress tracking**: Uses tqdm progress bar to show scraping progress
- **Batch processing**: Processes snapshots sequentially to avoid overwhelming the Wayback Machine API
- **Timeout handling**: 10-second timeout per HTTP request to Wayback Machine

## Dependencies

Required packages:
- `waybackpy`: For Wayback Machine CDX API access
- `requests`: For HTTP requests
- `beautifulsoup4`: For HTML parsing
- `tqdm`: For progress bars

Install with:
```bash
pip install waybackpy requests beautifulsoup4 tqdm
```

Or if using poetry:
```bash
poetry add waybackpy requests beautifulsoup4 tqdm
```

## Troubleshooting

### No snapshots found for URL

The Wayback Machine may not have archived the URL, or the `--from` date may be before the first snapshot. Check the Wayback Machine directly at https://web.archive.org/

### Extraction returns empty data

The CSS selectors may not match the archived page structure. The Wayback Machine may render pages differently than the live site. Check the archived page and update selectors if needed.

### Rate limiting errors

The Wayback Machine may rate-limit requests. The scraper includes delays between requests. If you encounter rate limiting, increase the delay or run at a different time.

### Import errors

Make sure all dependencies are installed:
```bash
pip install waybackpy requests beautifulsoup4 tqdm
```

## Future Enhancements

- Add support for custom CSS selectors per spider
- Add retry logic for failed snapshots
- Add filtering by date range
- Add export formats (CSV, Parquet)
- Add data validation and quality checks
