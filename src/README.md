# src/

<!-- AI agents: read src/docs/ai/ for codebase rules and navigation -->

Pacific Observatory source code. Three data pipelines share a common
core infrastructure, each following the same pattern:
**collect -> build -> publish**.

## Pipeline Status

| Pipeline | Directory | Status | CLI |
|----------|-----------|--------|-----|
| Text/EPU | `text/` | Live | `python run.py text {collect,build,publish}` |
| Fuel prices | `fuel/` | Planned (stub) | `python run.py fuel` prints "not yet migrated" |
| Supermarket CPI | `prices/` | Planned (stub) | `python run.py prices` prints "not yet migrated" |

Production fuel/prices code lives at `src/cpi/` with its own module CLI.

## Quick Start

```bash
# Scrape newspapers for a country or subregion
python run.py text collect --country ukraine --max-pages 3
python run.py text collect --subregion eastern_europe

# Compute EPU index (country only, or with aggregates)
python run.py text build --country ukraine --rebuild --cutoff-start-date 2020-01-01 --cutoff-end-date 2022-12-31
python run.py text build --subregion eastern_europe       # country + subregion aggregate

# Generate dashboard (writes dashboard_data.json + HTML)
python run.py text publish
python run.py text publish --country ukraine
```

Run `python run.py --help` or `python run.py text collect --help` for all options. The installed alias remains `po` after `poetry install`. See `text/README.md` for full flag reference.

## What Lives Here

| Directory | Pipeline | Description |
|-----------|----------|-------------|
| `configs/` | All | Cross-pipeline config: regions, countries, settings |
| `core/` | All | Shared infrastructure: config, storage, state, logging |
| `text/` | Text/EPU | Scrape newspapers, compute EPU indices, publish dashboards |
| `fuel/` | Fuel | *Planned* — migration target for fuel pipeline |
| `prices/` | Prices | *Planned* — migration target for prices pipeline |
| `cpi/` | Fuel + Prices | Production fuel/prices code (own CLI) |
| `ancillary_data/` | All | World Bank, IMF reference data (partial) |
| `cli.py` | All | Unified CLI entry point (`python run.py` locally, `po` installed) |

## Adding Sources

- Newspaper scraper: [text/HOW_TO_ADD_NEW_SCRAPER.md](text/HOW_TO_ADD_NEW_SCRAPER.md)
- Fuel fetcher: [fuel/HOW_TO_ADD_NEW_FETCHER.md](fuel/HOW_TO_ADD_NEW_FETCHER.md)
- Price spider: [prices/HOW_TO_ADD_NEW_SPIDER.md](prices/HOW_TO_ADD_NEW_SPIDER.md)

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.
