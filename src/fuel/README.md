# src/fuel/

Fuel price monitoring pipeline. Collects retail fuel prices from
government and industry sources, enriches them into standardized
time series, and publishes interactive dashboards.

## Data Flow

```
configs/{region}/{country}.yaml     → Source definitions
fetchers/{region}/{country}.py      → Fetch raw price observations
         ↓
collect.py                          → Deduplicate, append to per-source CSVs
         ↓
data/fuel/{country}/{source}/observations.csv
         ↓
process.py                          → Normalize products, derive families,
                                      enrich with ancillary data
         ↓
data/fuel/enriched/retail_series_enriched.csv
         ↓
publish.py                          → HTML dashboards, source catalogs
```

## Structure

```
fuel/
├── configs/               YAML source configs by region
│   ├── pacific/           Pacific region (24 countries)
│   ├── _examples/         Annotated config template
│   └── README.md
├── fetchers/              Per-country fetcher modules
│   ├── pacific/           Pacific region fetchers
│   ├── _common/           Shared utilities (PDF, dates)
│   ├── _examples/         Annotated fetcher template
│   └── README.md
├── collect.py             Collect stage: run fetchers, dedup, store
├── process.py             Build stage: raw → enriched
├── publish.py             Publish stage: dashboards
└── constants.py           Column schemas, product maps, palettes
```

## Commands

```bash
po fuel collect                     # Fetch all sources
po fuel collect --region pacific    # Fetch Pacific sources only
po fuel collect --source nz_mbie    # Fetch one source
po fuel build                       # Build enriched dataset
po fuel publish                     # Generate dashboards
po status                           # Check source health
```

## Adding a New Source

See [docs/fuel/HOW_TO_ADD_NEW_FETCHER.md](../../docs/fuel/HOW_TO_ADD_NEW_FETCHER.md)
