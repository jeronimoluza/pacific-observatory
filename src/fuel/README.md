# src/fuel/

> **Status: Planned** — not yet migrated. Stub files only.

Fuel price monitoring pipeline. Will collect retail fuel prices from
government and industry sources, enrich them into standardized time
series, and publish interactive dashboards.

## Target Structure

```
fuel/
├── configs/        Per-region/country YAML source configs
├── fetchers/       Per-country data fetchers
├── collect.py      Collect stage
├── process.py      Build stage
└── publish.py      Publish stage
```

## Current Production Code

The working fuel pipeline lives at `src/cpi/fuel_prices/` with its own
module CLI. See `src/cpi/fuel_prices/README.md`.
