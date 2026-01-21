# Text Module

Newspaper scraping and Economic Policy Uncertainty (EPU) analysis for the Pacific Observatory.

## Quick Start

```bash
# Scrape a single newspaper
poetry run python -m text.scrapers.orchestration.main fiji_sun

# Scrape with update mode (only new articles)
poetry run python -m text.scrapers.orchestration.main fiji_sun --mode update

# Check scraper status
poetry run python -m text.scrapers.orchestration.status

# Run EPU analysis
poetry run python -m text.analysis.main
```

## Module Structure

```
src/text/
├── core/                      # Core utilities and infrastructure
│   ├── logging_config.py      # Structured logging
│   ├── run_tracker.py         # SQLite run tracking
│   ├── events.py              # Event emission system
│   ├── errors.py              # Error hierarchy
│   ├── circuit_breaker.py     # Resilience patterns
│   └── checkpoints.py         # Checkpoint/resume system
├── scrapers/                  # Web scraping framework
│   ├── newspaper_scraper.py   # Main scraper orchestrator
│   ├── client_http.py         # Async HTTP client
│   ├── client_browser.py      # Selenium browser client
│   ├── listing_strategies.py  # URL discovery strategies
│   ├── parser.py              # HTML data extraction
│   ├── factory.py             # Scraper factory
│   ├── models.py              # Pydantic data models
│   ├── configs/               # YAML newspaper configs
│   ├── pipelines/             # Data processing
│   │   ├── storage.py         # CSV storage
│   │   └── cleaning.py        # Data cleaning functions
│   └── orchestration/         # CLI and batch processing
├── analysis/                  # EPU and text analysis
│   ├── main.py                # Analysis entry point
│   ├── epu.py                 # EPU index calculation
│   ├── modeling.py            # LASSO regression
│   └── sentiment.py           # Sentiment analysis
└── plotting/                  # Interactive visualizations
```

## Documentation

- [Adding a Newspaper](docs/adding_a_newspaper.md) - Step-by-step guide
- [Config Schema](docs/config_schema.md) - YAML config reference
- [Architecture](docs/architecture.md) - System overview

## Commands

### Scraping

```bash
# Single newspaper
poetry run python -m text.scrapers.orchestration.main fiji_sun

# With mode (full, update, discover)
poetry run python -m text.scrapers.orchestration.main fiji_sun --mode update

# All newspapers in a country
poetry run python -m text.scrapers.orchestration.main --country fiji

# All newspapers
poetry run python -m text.scrapers.orchestration.main --run-all

# List available scrapers
poetry run python -m text.scrapers.orchestration.main --list
```

### Monitoring

```bash
# Recent runs (last 24 hours)
poetry run python -m text.scrapers.orchestration.status

# Last N hours
poetry run python -m text.scrapers.orchestration.status --hours 48

# Only failures
poetry run python -m text.scrapers.orchestration.status --failures

# Specific newspaper
poetry run python -m text.scrapers.orchestration.status --newspaper fiji_sun

# Aggregate statistics
poetry run python -m text.scrapers.orchestration.status --stats
```

### Validation

```bash
# Validate a config file
poetry run python -m text.scrapers.orchestration.validate configs/fiji/fiji_sun.yaml
```

### Analysis

```bash
# Run EPU analysis for all countries
poetry run python -m text.analysis.main

# Specific country
poetry run python -m text.analysis.main --country fiji
```

## Makefile Shortcuts

```bash
make test              # Run unit tests
make test-integration  # Run integration tests
make lint              # Run linters
make format            # Format code
make scrape NEWSPAPER=fiji_sun
make status            # View scraper status
make validate CONFIG=path/to/config.yaml
```

## Data Directory

Scraped data is stored in `data/text/`:

```
data/text/
├── fiji/
│   ├── fiji_sun/
│   │   ├── news.csv        # Article data
│   │   ├── urls.csv        # Discovered URLs
│   │   ├── metadata.json   # Scrape metadata
│   │   └── failed.csv      # Failed URLs
│   └── fiji_times/
│       └── ...
├── cambodia/
│   └── ...
└── scraper_runs.db         # Run tracking database
```

## Configuration

Newspapers are configured via YAML files in `src/text/scrapers/configs/`.

See [Config Schema](docs/config_schema.md) for the full reference.

Example:
```yaml
name: fiji_sun
country: fiji
language: en
base_url: https://fijisun.com.fj

client: http
concurrency: 10
rate_limit: 0.5

listing:
  type: pagination
  start_url: /category/local-news
  page_param: page

thumbnails:
  container: article.news-item
  title: h2.title
  link: a
  date: span.date

article:
  title: h1.article-title
  body: div.article-body
  date: time.publish-date
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run only unit tests
poetry run pytest tests/unit -v

# Run with coverage
poetry run pytest --cov=src/text --cov-report=html

# Run tests for a specific module
poetry run pytest tests/unit/test_cleaning.py -v
```

## Development

See the [Architecture](docs/architecture.md) documentation for an overview of the system design.

When adding a new newspaper:
1. Read [Adding a Newspaper](docs/adding_a_newspaper.md)
2. Create a YAML config file
3. Validate with `poetry run python -m text.scrapers.orchestration.validate`
4. Test with a limited scrape
5. Commit and document
