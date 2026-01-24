# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Pacific Observatory is a World Bank analytical program exploring alternative data sources to mitigate data gaps in official statistics for Papua New Guinea and Pacific Island Countries. The repository contains multiple research topics with code, notebooks, and outputs structured by theme.

## Development Environment

### Setup
```bash
# Install dependencies with Poetry
poetry install

# Install with specific dependency groups
poetry install --with scraping
poetry install --with testing
poetry install --with docs

# Install pre-commit hooks
pre-commit install
```

### Python Version
- Requires Python 3.11+
- Managed via Poetry (pyproject.toml)

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run unit tests only
poetry run pytest tests/unit/ -v

# Run specific test file
poetry run pytest tests/unit/test_timeout_handling.py -v

# Run with coverage
poetry run pytest --cov=src/text --cov-report=html

# Run integration tests (slower, requires network)
poetry run pytest tests/test_scrapers.py -v

# Run tests by marker
poetry run pytest -m unit          # Unit tests only
poetry run pytest -m integration   # Integration tests only
poetry run pytest -m "not slow"    # Skip slow tests
```

## Text Module (Newspaper Scraping)

The text module is the primary active component. It scrapes 50+ Pacific newspapers weekly to calculate Economic Policy Uncertainty (EPU) indices.

### Architecture

**3-Layer Structure (recently refactored):**

```
src/text/scrapers/
├── scraper.py              # Main orchestrator (was newspaper_scraper.py)
├── modes.py                # ScrapeMode enum (UPDATE, RESUME, FULL_DISCOVERY, FULL_FROM_SCRATCH)
├── discovery.py            # URL discovery orchestration
├── extraction.py           # Article extraction orchestration
├── strategies/             # Listing discovery strategies (was listing_strategies.py)
│   ├── base.py            # BaseListingStrategy
│   ├── pagination.py      # Page number-based pagination
│   ├── archive.py         # Date-based archives
│   ├── api.py             # JSON API endpoints
│   └── follow_link.py     # "Next page" button following
├── pipelines/
│   ├── cleaning/          # Data cleaning by country (was cleaning.py)
│   │   ├── registry.py   # @register_cleaner decorator
│   │   ├── common.py     # Generic utilities
│   │   └── [country].py  # Country-specific cleaners
│   └── storage/           # CSV/JSON storage (was storage.py)
│       ├── csv_writer.py
│       ├── metadata.py
│       └── urls.py
├── orchestration/         # CLI scripts for running scrapers
│   ├── main.py           # Main entry point
│   ├── run_scraper.py    # Single scraper runner
│   ├── run_multiple.py   # Batch runner with timeout handling
│   ├── summary.py        # Run summary formatting
│   ├── failure_log.py    # Failure logging to JSON
│   ├── validate.py       # Config validation
│   └── status.py         # Status checking
└── configs/              # YAML configs organized by country
    └── [country]/
        └── [newspaper].yaml
```

**Key Design Patterns:**
- **Config-driven architecture**: Each newspaper has a YAML config defining selectors and strategy
- **Strategy pattern**: Different listing strategies (pagination, archive, API, follow_link)
- **Registry pattern**: Cleaning functions auto-register using `@register_cleaner` decorator
- **Delegation pattern**: Main scraper delegates to discovery and extraction orchestrators
- **CSV stability**: Output CSV format must remain unchanged (critical for downstream reports)

### Running Scrapers

```bash
# Using Python module syntax
poetry run python -m text.scrapers.orchestration.main sibc
poetry run python -m text.scrapers.orchestration.main fiji_sun --update
poetry run python -m text.scrapers.orchestration.main --run-all

# Using Makefile (from src/ directory)
cd src
make scrape NEWSPAPER=fiji_sun          # Default mode
make scrape-update NEWSPAPER=fiji_sun   # Update mode only
make scrape-all                         # All newspapers

# Run modes (consolidated)
--update              # Discover new + scrape new (default Friday run)
--resume              # Use existing urls.csv + scrape pending
--full-discovery      # Discover all + overwrite urls.csv (no scraping)
--full-from-scratch   # Discover all + scrape all (nuclear option)

# Timeout control
--timeout 1800        # 30-minute timeout per scraper (default: 600s)

# List available scrapers
python -m text.scrapers.orchestration.main --list-scrapers
python -m text.scrapers.orchestration.main --list-countries
```

### Config Validation

```bash
# Validate single config
poetry run python -m text.scrapers.orchestration.validate src/text/scrapers/configs/fiji/fiji_sun.yaml

# Validate all configs
poetry run python -m text.scrapers.orchestration.validate --all

# Validate with live HTTP request
poetry run python -m text.scrapers.orchestration.validate fiji_sun.yaml --live

# Using Makefile
cd src
make validate CONFIG=text/scrapers/configs/fiji/fiji_sun.yaml
make validate-all
```

### Checking Status

```bash
# View recent runs
poetry run python -m text.scrapers.orchestration.status --last-24h

# View failures
poetry run python -m text.scrapers.orchestration.status --failures

# View aggregate statistics
poetry run python -m text.scrapers.orchestration.status --stats

# Database overview
poetry run python -m text.scrapers.orchestration.check_database

# Using Makefile
cd src
make status
make status-failures
make status-stats
make check-text-database
```

### Adding a New Newspaper

**See comprehensive guides:**
- `src/text/docs/adding_a_newspaper.md` - 7-step quick-start (<30 min)
- `src/text/docs/config_schema.md` - Complete config reference (1019 lines)

**Quick workflow:**
1. Analyze the site (5 min) - Determine listing strategy
2. Copy similar config (2 min) - Based on strategy type
3. Modify config (10 min) - Update selectors and URLs
4. Validate (3 min) - `make validate CONFIG=path/to/config.yaml`
5. Test scrape (5 min) - `make scrape NEWSPAPER=name`
6. Add cleaning functions if needed (5 min) - In `pipelines/cleaning/[country].py`
7. Commit (2 min)

**Four listing strategies:**
- `pagination`: URL contains page number (`?page=1`, `/page/2/`)
- `archive`: URL contains dates (`/2024/01/`, `/2024/02/`)
- `api`: JSON API endpoints (check Network tab)
- `follow_link`: "Next page" button with href

## Code Quality

### Pre-commit Hooks
```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
```

**Enabled hooks:**
- `ruff` - Fast linting (replaces flake8)
- `ruff-format` - Fast formatting (replaces black)
- `bandit` - Security checks
- `trailing-whitespace`, `end-of-file-fixer`
- `check-yaml`, `check-json`, `check-ast`
- `detect-aws-credentials`, `detect-private-key`

### Linting and Formatting
```bash
# Ruff linting (runs via pre-commit)
poetry run ruff check src/

# Ruff formatting (runs via pre-commit)
poetry run ruff format src/

# Type checking with mypy
poetry run mypy src/text/
```

## Import Paths (Updated After Refactoring)

**IMPORTANT: Deprecated imports have been removed. Use new paths:**

```python
# Correct imports (post-refactoring)
from text.scrapers.scraper import NewspaperScraper
from text.scrapers.strategies import create_listing_strategy, PaginationStrategy
from text.scrapers.pipelines.cleaning import clean_html_text, get_cleaning_func
from text.scrapers.pipelines.storage import CSVStorage

# Old imports NO LONGER WORK (removed in latest refactoring)
from text.scrapers.newspaper_scraper import NewspaperScraper  # ❌ ModuleNotFoundError
from text.scrapers.listing_strategies import ...              # ❌ ModuleNotFoundError
```

## Critical Constraints

1. **CSV Output Format**: The text scraper CSV output format MUST remain unchanged. Field order, headers, and delimiters are critical for downstream reports and analysis. Breaking this will break EPU index calculations.

2. **Config File Compatibility**: All existing YAML configs must continue to work without modification. The config schema can be extended but not changed in breaking ways.

3. **Weekly Friday Runs**: The text scraping pipeline runs manually every Friday. Reliability and clear failure reporting are more important than automation.

## Data Paths

- Text scraping output: `data/text/`
- Scraper configs: `src/text/scrapers/configs/[country]/[newspaper].yaml`
- Failure logs: `data/text/last_run_failures.json`
- Run logs: `logs/`

## Other Modules

**CPI Module** (`src/cpi/`):
- Consumer Price Index price scraping and analysis
- Uses Scrapy for web scraping
- Run with: `poetry run python src/cpi/price_scraping/run_spider.py [spider_name]`

**Tourism Module** (`src/tourism/`):
- Tourism statistics and Google Trends analysis
- Parsers for NSO PDFs from Fiji, Tonga, Vanuatu

## Documentation

- `README.md` - Project overview and research topics
- `src/text/docs/config_schema.md` - Complete newspaper config reference
- `src/text/docs/adding_a_newspaper.md` - Quick-start guide for adding newspapers
- `TEXT_PLAN_V2.md` - Text module refactoring plan (3 layers)
- `PR_description.md` - Recent refactoring PR description

## License

Materials are open-source under MIT license. See LICENSE.md.
