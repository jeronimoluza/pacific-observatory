# CPI Supermarket Scrape Analysis

This folder contains documentation and code to analyze scraped supermarket price observations that have been classified into COICOP categories.

## Running reports

Run from the project root:

```bash
poetry run python src/cpi/analysis/run_reports.py \
  --input data/cpi/analysis/all_countries_supermarket_prices.csv \
  --outdir data/cpi/analysis/reports
```

Architecture:

- `run_reports.py`: orchestration layer (I/O, file writing)
- `functions.py`: pure data wrangling/statistics functions
- `coicop_utils.py`: COICOP code mapping and hierarchy utilities
