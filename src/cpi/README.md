# Price Atlas Implementation

`src/cpi/` is the implementation home behind the public `price_atlas` surface. It combines retailer prices, fuel prices, product enrichment, index construction, and publishable outputs into one pipeline.

## Shared Goal

- Collect price evidence from public sources.
- Normalize it into stable tables and storage layouts.
- Enrich it with quantities, classifications, and quality signals.
- Analyze it into CPI-style indicators and supporting reports.
- Publish artifacts people can inspect, compare, and ship.

## Pipeline Map

| Stage | Main folders | What happens here |
| --- | --- | --- |
| `collect` | `price_scraping/`, `fuel_prices/fetchers/` | Pull raw retailer, Wayback, and fuel observations from source systems. |
| `normalize` | `fuel_prices/`, `price_scraping/` | Turn raw source outputs into canonical observation tables and stable storage layouts. |
| `enrich` | `coicopping/` | Add standardized quantities, usability flags, and COICOP classifications. |
| `analyze` | `price_index/`, `analysis/` | Build indices, comparisons, and analytical report outputs. |
| `publish` | `fuel_prices/`, `visualization/` | Regenerate HTML dashboards, policy overviews, and other outward-facing artifacts. |

## Main Interactions

The target public commands should read like:

- `po price_atlas update`
- `po price_atlas normalize`
- `po price_atlas enrich`
- `po price_atlas analyze`
- `po price_atlas publish`

Inside `src/cpi/`, the implementation still lives in local modules and scripts. Use the local docs below for the real entry points today.

## Folder Guide

- `price_scraping/` - retailer and Wayback collection.
- `fuel_prices/` - fuel collection, backfills, cleanup, and publish artifacts.
- `coicopping/` - quantity extraction and COICOP enrichment.
- `price_index/` - CPI construction from enriched supermarket price data.
- `analysis/` - broader analytical reporting and cross-country work.
- `visualization/` - standalone CPI coverage dashboards and tables.
- `imf_data/` - IMF comparison helpers and data access utilities.

## Read Next

- `src/cpi/fuel_prices/README.md`
- `src/cpi/price_scraping/README.md`
- `src/cpi/coicopping/README.md`
- `src/cpi/price_index/README.md`
- `src/cpi/visualization/README.md`
