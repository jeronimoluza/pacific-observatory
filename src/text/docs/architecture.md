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


## Analysis Module (`src/text/analysis/`)

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
| category | string | Article category |
| scraped_at | string | Scrape timestamp |

**urls.csv:**
| Column | Type | Description |
|--------|------|-------------|
| url | string | Article URL |
| title | string | Article title |
| date | string | Publication date |
