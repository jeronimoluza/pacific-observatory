# Architecture

Pacific Observatory is organized as three data pipelines sharing a
common core infrastructure. Each pipeline follows the same pattern:
**collect → build → publish**.

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                      po CLI                              │
│  po fuel {collect,build,publish}                         │
│  po text {collect,build,publish}                         │
│  po prices {collect,build,publish}                       │
│  po status | po init --region <name>                     │
└────┬──────────────┬──────────────┬──────────────────────┘
     │              │              │
┌────▼────┐   ┌────▼────┐   ┌────▼─────┐
│  fuel/  │   │  text/  │   │  prices/ │
│         │   │         │   │          │
│ collect │   │ collect │   │ collect  │   ← Fetch/scrape from sources
│ process │   │ process │   │ process  │   ← Enrich, classify, compute
│ publish │   │ publish │   │ publish  │   ← Dashboards, outputs
└────┬────┘   └────┬────┘   └────┬─────┘
     │              │              │
┌────▼──────────────▼──────────────▼──────┐
│                 core/                    │
│  config  storage  state  hashing        │
│  http    logging                        │
└────┬────────────────────────────────────┘
     │
┌────▼────────────────────────────────────┐
│              src/configs/                │
│  countries.yaml  regions.yaml           │
│  settings.yaml                          │
└─────────────────────────────────────────┘
```

## Pipeline Pattern

Every pipeline implements three stages:

| Stage | What it does | CLI command |
|-------|-------------|-------------|
| **collect** | Fetch new data from external sources | `po {pipeline} collect` |
| **build** | Process raw data into analysis-ready outputs | `po {pipeline} build` |
| **publish** | Generate dashboards and HTML artifacts | `po {pipeline} publish` |

## Directory Layout

```
src/
├── configs/          Cross-pipeline: countries, regions, settings
├── core/             Shared infrastructure (config, storage, state, etc.)
├── fuel/             Fuel price monitoring pipeline
│   ├── configs/      Per-region/country YAML source configs
│   ├── fetchers/     Per-country data fetchers
│   ├── collect.py    Collect stage
│   ├── process.py    Build stage
│   └── publish.py    Publish stage
├── text/             Newspaper EPU analysis pipeline
│   ├── configs/      Per-region/country/newspaper YAML configs
│   ├── scrapers/     HTTP/browser scraping framework
│   ├── analysis/     EPU, sentiment, topic indices
│   ├── collect.py    Collect stage
│   ├── process.py    Build stage
│   └── publish.py    Publish stage
├── prices/           Supermarket prices → CPI pipeline
│   ├── configs/      Per-region/country/retailer YAML configs
│   ├── scrapers/     Scrapy spiders
│   ├── coicop/       COICOP classification
│   ├── index/        CPI construction
│   ├── collect.py    Collect stage
│   ├── process.py    Build stage
│   └── publish.py    Publish stage
├── ancillary_data/   World Bank, IMF data loaders
└── cli.py            Unified `po` CLI entry point
```

## Data Layout

```
data/
├── fuel/{country}/{source}/observations.csv
├── text/{country}/{newspaper}/news.csv
├── prices/{country}/{retailer}/raw_items/
├── ancillary_data/worldbank/
└── ancillary_data/imf/
```

## Core Modules

| Module | Responsibility |
|--------|---------------|
| `core/config.py` | Load YAML configs, discover pipeline sources |
| `core/storage.py` | Per-source paths, CSV I/O, slug helpers |
| `core/state.py` | Track source freshness, staleness assessment |
| `core/hashing.py` | Observation dedup via SHA-256 |
| `core/http.py` | HTTP session with browser-like headers |
| `core/logging.py` | Structured file logging per source |

## Technologies

| Layer | Technology |
|-------|-----------|
| Configuration | YAML + Pydantic validation |
| Data processing | pandas, numpy |
| Fuel fetching | requests, BeautifulSoup, pdfplumber |
| Text scraping | httpx (async), Selenium |
| Price scraping | Scrapy, Scrapy-Playwright |
| Classification | Google Gemini AI |
| Visualization | Plotly, matplotlib |
| CLI | Click |
| Testing | pytest |
| Package management | Poetry / pip |
