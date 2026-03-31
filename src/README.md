# src/

Pacific Observatory source code. Three data pipelines share a
common core infrastructure, each following the same pattern:
**collect → build → publish**.

## What Lives Here

| Directory | Pipeline | Description |
|-----------|----------|-------------|
| `configs/` | All | Cross-pipeline config: countries, regions, settings |
| `core/` | All | Shared infrastructure: config loading, storage, state, logging |
| `fuel/` | Fuel prices | Collect retail fuel prices, enrich, publish dashboards |
| `text/` | Text/EPU | Scrape newspapers, compute EPU indices, publish dashboards |
| `prices/` | Supermarket CPI | Scrape retailers, classify (COICOP), build CPI |
| `ancillary_data/` | All | World Bank, IMF reference data loaders |
| `cli.py` | All | Unified `po` CLI entry point |

## Commands

```bash
po fuel collect                  # Fetch fuel price data
po fuel build                    # Enrich into standardized series
po fuel publish                  # Generate dashboards

po text collect --country fiji   # Scrape Fiji newspapers
po text build --country fiji     # Compute EPU index
po text publish                  # Generate dashboards

po prices collect --country fiji # Scrape supermarket prices
po prices build --country fiji   # Classify + build CPI
po prices publish                # Generate CPI dashboards

po status                        # Source health across all pipelines
po init --region <name>          # Scaffold a new region
```

## Adding Sources

Each pipeline has a HOW_TO guide:
- Fuel fetcher: [docs/fuel/HOW_TO_ADD_NEW_FETCHER.md](../docs/fuel/HOW_TO_ADD_NEW_FETCHER.md)
- Newspaper scraper: [docs/text/HOW_TO_ADD_NEW_SCRAPER.md](../docs/text/HOW_TO_ADD_NEW_SCRAPER.md)
- Price spider: [docs/prices/HOW_TO_ADD_NEW_SPIDER.md](../docs/prices/HOW_TO_ADD_NEW_SPIDER.md)

## Architecture

See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the full system design.
