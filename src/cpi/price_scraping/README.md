# price_scraping - Web-Based Inflation Tracker

A Python-based web scraping pipeline for collecting daily price data from online retailers and reconstructing historical price series using the Wayback Machine.

## Quick Start

### Prerequisites
- Python 3.11+
- Poetry (for dependency management)

### Installation

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Running the Spiders

### Basic Usage

Run the MH Online spider with default settings:

```bash
scrapy crawl mh_online
```

Or use the convenience script:

```bash
python run_spider.py mh_online
```

### Common Commands

**Limit crawl to 50 pages:**
```bash
scrapy crawl mh_online -s CLOSESPIDER_PAGECOUNT=50
```

**Increase download delay to 5 seconds:**
```bash
scrapy crawl mh_online -s DOWNLOAD_DELAY=5
```

**Reduce concurrent requests to 4:**
```bash
scrapy crawl mh_online -s CONCURRENT_REQUESTS=4
```

**Change output directory:**
```bash
scrapy crawl mh_online -s OUTPUT_DIR=data/custom_output
```

### Using the run_spider.py Script

The `run_spider.py` script provides a convenient interface with common options. **Note:** Run from the project root directory.

```bash
# Basic run (outputs to data/cpi/price_scraping/{country}/{spider_name}/raw_items/)
poetry run python src/cpi/price_scraping/run_spider.py mh_online

# With custom delay (seconds)
poetry run python src/cpi/price_scraping/run_spider.py mh_online --delay 3

# With concurrent request limit
poetry run python src/cpi/price_scraping/run_spider.py mh_online --concurrent 4

# With page limit
poetry run python src/cpi/price_scraping/run_spider.py mh_online --limit 100

# With custom output directory (relative to project root)
poetry run python src/cpi/price_scraping/run_spider.py mh_online --output-dir data/custom_output

# Combine options
poetry run python src/cpi/price_scraping/run_spider.py mh_online --delay 3 --concurrent 4 --limit 50
```

## Output

Scraped data is saved in JSONL format (one JSON object per line) organized by country and spider:

- **Directory structure:** `data/cpi/price_scraping/{country}/{spider_name}/raw_items/`
- **Filename format:** `{spider_name}_YYYYMMDD_HHMMSS.jsonl`
- **Example location:** `data/cpi/price_scraping/fiji/mh_online/raw_items/mh_online_20251119_132552.jsonl`

Example output:
```json
{"product_id": "12345", "product_name": "Product Name", "price": "10.99", "category": "Electronics > Computers", "url": "https://mh.com.fj/product/12345", "url_hash": "abc123...", "scraped_at": "2024-01-15 10:30:00"}
{"product_id": "12346", "product_name": "Another Product", "price": "25.50", "category": "Electronics > Computers", "url": "https://mh.com.fj/product/12346", "url_hash": "def456...", "scraped_at": "2024-01-15 10:30:15"}
```

## Project Overview

This project aims to create a proof-of-concept inflation tracker that:
- Scrapes product prices from e-commerce sites using **Scrapy**
- Integrates historical data from the **Wayback Machine**
- Generates synthetic price indices for economic analysis
- Provides a scalable, reproducible data pipeline

**Current Focus:** MH Online (Fiji) - https://mh.com.fj/

## Project Structure

```
price_scraping/
├── price_scraping/
│   ├── __init__.py
│   ├── settings.py              # Scrapy configuration
│   ├── items.py                 # Item definitions
│   ├── pipelines.py             # Data processing pipelines
│   ├── middlewares.py           # Custom middleware
│   ├── utils.py                 # Utility functions
│   └── spiders/
│       ├── __init__.py
│       └── mh_online.py         # MH Online spider
├── data/                        # Output directory for scraped data
├── pyproject.toml               # Project dependencies (Poetry)
├── scrapy.cfg                   # Scrapy configuration
├── run_spider.py                # Convenience script for running spiders
├── statement.md                 # Project statement
└── README.md                    # This file
```

## Configuration

### Default Settings

Edit `price_scraping/settings.py` to customize:

- **CONCURRENT_REQUESTS**: Number of parallel requests (default: 16)
- **DOWNLOAD_DELAY**: Delay between requests in seconds (default: 2)
- **USER_AGENT**: Browser identification string
- **ROBOTSTXT_OBEY**: Whether to respect robots.txt (default: True)
- **AUTOTHROTTLE_ENABLED**: Automatic throttling based on server response (default: True)
- **RETRY_TIMES**: Number of retries on failure (default: 3)
- **DOWNLOAD_TIMEOUT**: Request timeout in seconds (default: 15)

### Spider-Specific Settings

**mh_online.py:**
- Starts at: `https://mh.com.fj/shop/`
- Follows: Product pages matching `/product/.*`
- Extracts: Product name, price, category, product ID, URL

## Data Pipeline

The data processing pipeline includes three stages:

1. **DuplicationPipeline**: Removes duplicate URLs using MD5 hashing
2. **JsonWriterPipeline**: Writes items to timestamped JSONL files
3. **LoggingPipeline**: Logs processing statistics

## Utilities

The `price_scraping/utils.py` module provides helper functions:

- `extract_price()`: Parse numeric price from text
- `extract_currency()`: Identify currency code
- `generate_url_hash()`: Create URL hash for deduplication
- `generate_version_hash()`: Track HTML content changes
- `parse_timestamp()`: Parse HTTP timestamps
- `normalize_category()`: Standardize category names

## Troubleshooting

### Spider not finding products
- Check CSS selectors in `price_scraping/spiders/mh_online.py`
- Inspect website HTML to verify element classes/IDs
- Enable debug logging: `LOG_LEVEL = "DEBUG"` in settings.py
- Run with: `scrapy crawl mh_online -s LOG_LEVEL=DEBUG`

### Rate limiting / 429 errors
- Increase `DOWNLOAD_DELAY` in settings.py or via command line
- Reduce `CONCURRENT_REQUESTS`
- Enable `AUTOTHROTTLE_ENABLED = True` (already enabled by default)

### Memory issues
- Reduce `CONCURRENT_REQUESTS`
- Enable `MEMDEBUG_ENABLED = True` to monitor memory usage
- Limit crawl with `CLOSESPIDER_PAGECOUNT`

### Connection timeouts
- Increase `DOWNLOAD_TIMEOUT` in settings.py
- Increase `RETRY_TIMES` for more retry attempts
- Check network connectivity

## Next Steps

1. **Wayback Machine integration**: Add historical data retrieval
2. **Data processing**: Build aggregation and analysis pipeline
3. **Price index generation**: Create synthetic inflation indices
4. **Visualization**: Build dashboards for price trends
5. **Multi-site support**: Extend to additional retailers

## Dependencies

- **scrapy** (>=2.13.3): Web scraping framework
- **poetry**: Dependency management

## License

TBD

## Author

Jerónimo Luza
