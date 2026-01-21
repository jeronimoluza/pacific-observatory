# Text Module Architecture

This document provides an overview of the text module's architecture, components, and data flow.

## System Overview

```
                                 ┌─────────────────┐
                                 │   YAML Config   │
                                 └────────┬────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Scraper Factory                          │
│  Creates configured NewspaperScraper with appropriate client    │
└─────────────────────────────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
          │  Listing        │   │  HTTP Client    │   │  Browser Client │
          │  Strategy       │   │  (httpx)        │   │  (Selenium)     │
          └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
                   │                     │                     │
                   └─────────────────────┼─────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   Parser            │
                              │   Extract data from │
                              │   HTML/JSON         │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Cleaning Pipeline  │
                              │  Normalize data     │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   CSV Storage       │
                              │   Persist articles  │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   EPU Analysis      │
                              │   Calculate index   │
                              └─────────────────────┘
```

## Core Components

### 1. Core Module (`src/text/core/`)

Infrastructure and cross-cutting concerns.

#### Logging (`logging_config.py`)
- Structured JSON logging for machine parsing
- Console output for interactive use
- Correlation IDs for request tracing
- Log rotation and file management

#### Run Tracking (`run_tracker.py`)
- SQLite database for tracking runs
- Records success/failure counts
- Stores timing and error information
- Enables historical analysis

#### Events (`events.py`)
- Publish-subscribe event system
- Decoupled observability hooks
- Built-in handlers for logging and database

#### Error Handling (`errors.py`)
- Hierarchical exception classes
- Rich context in exceptions
- Enables granular error handling

#### Circuit Breaker (`circuit_breaker.py`)
- Prevents cascading failures
- Automatic recovery testing
- Per-newspaper isolation

#### Checkpoints (`checkpoints.py`)
- Saves scraping progress
- Enables resuming interrupted runs
- Tracks pending URLs

### 2. Scrapers Module (`src/text/scrapers/`)

Web scraping implementation.

#### NewspaperScraper (`newspaper_scraper.py`)
Central orchestrator that coordinates:
- URL discovery via listing strategies
- Article fetching via clients
- Data extraction via parser
- Data cleaning via pipeline
- Storage via CSVStorage

**Operation Modes:**
- `full`: Complete scrape of all discoverable articles
- `update`: Only scrape new articles since last run
- `discover`: URL discovery only, no article scraping
- `resume`: Resume from checkpoint

#### Clients

**HTTP Client (`client_http.py`):**
- Async HTTP using `httpx`
- Concurrent requests with semaphore
- Rate limiting and retry logic
- Cookie management

**Browser Client (`client_browser.py`):**
- Selenium WebDriver
- JavaScript rendering support
- Cookie handling from browser

#### Listing Strategies (`listing_strategies.py`)

| Strategy | Description |
|----------|-------------|
| `PaginationStrategy` | Numbered page navigation |
| `ArchiveStrategy` | Date-based archives |
| `SearchStrategy` | Search result pages |
| `CategoryStrategy` | Category listings |
| `ApiStrategy` | JSON API endpoints |

#### Parser (`parser.py`)
- CSS selector extraction
- XPath support
- Attribute extraction
- Multiple element handling

#### Pipelines (`pipelines/`)

**Storage (`storage.py`):**
- CSV file operations
- Streaming writes
- Metadata management
- Deduplication

**Cleaning (`cleaning.py`):**
- Date normalization
- Text cleaning
- URL resolution
- Newspaper-specific cleaners

### 3. Analysis Module (`src/text/analysis/`)

Text analysis and EPU calculation.

#### EPU (`epu.py`)
Economic Policy Uncertainty index calculation:
1. Load articles from CSV
2. Count articles matching EPU terms
3. Calculate ratio per newspaper
4. Standardize and aggregate

#### Modeling (`modeling.py`)
- LASSO regression for inflation prediction
- Topic modeling with LDA
- Sentiment analysis with VADER

## Data Flow

### Scraping Flow

```
1. Load Config
   └─> Parse YAML configuration file

2. Create Scraper
   └─> Factory creates NewspaperScraper with:
       - Client (HTTP or Browser)
       - Listing Strategy
       - Parser
       - Storage

3. Discover URLs
   └─> Strategy discovers article URLs from listing pages
   └─> URLs saved to urls.csv

4. Scrape Articles
   └─> For each URL:
       a. Fetch page content
       b. Parse with selectors
       c. Clean extracted data
       d. Append to news.csv

5. Track Results
   └─> Update run_tracker database
   └─> Save checkpoint if enabled
```

### Analysis Flow

```
1. Load Data
   └─> Read news.csv files for each newspaper

2. Preprocess
   └─> Clean text
   └─> Tokenize

3. Match Terms
   └─> Count EPU keyword matches
   └─> Count total articles

4. Calculate Index
   └─> Compute ratio per newspaper
   └─> Standardize to z-scores
   └─> Aggregate across newspapers

5. Output
   └─> Save results to CSV/JSON
```

## Configuration

### YAML Config Structure

```yaml
# Identity
name: newspaper_name
country: country_code
language: language_code
base_url: https://example.com

# Client settings
client: http|browser
concurrency: 10
rate_limit: 0.5

# Discovery
listing:
  type: pagination|archive|api
  start_url: /news
  ...

# Selectors
thumbnails:
  container: selector
  title: selector
  ...

article:
  title: selector
  body: selector
  ...

# Cleaning
cleaning:
  date: function_name
  body: function_name
```

## Data Storage

### Directory Structure

```
data/text/
├── {country}/
│   └── {newspaper}/
│       ├── news.csv          # Article data
│       ├── urls.csv          # Discovered URLs
│       ├── metadata.json     # Scrape metadata
│       └── failed.csv        # Failed URLs
├── scraper_runs.db           # Run tracking database
└── checkpoints/              # Resume checkpoints
```

### CSV Schema

**news.csv:**
| Column | Type | Description |
|--------|------|-------------|
| url | string | Article URL |
| title | string | Article title |
| body | string | Article content |
| date | string | Publication date (YYYY-MM-DD) |
| author | string | Author name |
| category | string | Article category |
| scraped_at | string | Scrape timestamp |

**urls.csv:**
| Column | Type | Description |
|--------|------|-------------|
| url | string | Article URL |
| title | string | Article title |
| date | string | Publication date |
| discovered_at | string | Discovery timestamp |

## Error Handling

### Exception Hierarchy

```
TextModuleError
├── ScraperError
│   ├── NetworkError
│   │   └── RateLimitError
│   └── ParseError
├── ConfigError
├── StorageError
├── AnalysisError
├── CircuitOpenError
└── CheckpointError
```

### Recovery Strategies

1. **Retry**: Automatic retries with exponential backoff
2. **Circuit Breaker**: Stop failing requests, attempt recovery
3. **Checkpoint**: Resume from saved progress
4. **Graceful Degradation**: Log and continue on non-critical errors

## Observability

### Logging

- JSON structured logs for machine parsing
- Console output for human reading
- Correlation IDs for request tracing
- Configurable log levels

### Metrics

Run tracker provides:
- Run counts per newspaper
- Success/failure rates
- Article counts over time
- Timing information

### Status CLI

```bash
python -m text.scrapers.orchestration.status
```

Shows:
- Recent runs
- Failures
- Aggregate statistics

## Extensibility

### Adding a New Listing Strategy

1. Create class extending `ListingStrategy`
2. Implement `discover()` method
3. Register in factory

### Adding a New Cleaning Function

1. Define function in `cleaning.py`
2. Register in `CLEANING_FUNCTIONS` dict
3. Reference in config

### Adding a New Client Type

1. Create class implementing client protocol
2. Add to factory client selection
3. Document in config schema
