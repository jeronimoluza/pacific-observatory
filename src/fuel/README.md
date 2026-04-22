# src/fuel/

> **Status: Active migration target** — `collect` and `build` now use the canonical fuel hierarchy.

Fuel price monitoring pipeline. Will collect retail fuel prices from
government and industry sources, enrich them into standardized time
series, and publish interactive dashboards.

## Target Structure

```
fuel/
├── configs/        Per-source YAML configs at {region}/{subregion}/{country}/{source}.yaml
├── fetchers/       Canonical wrapper modules at {region}/{subregion}/{country}/{source}.py
├── collect.py      Collect stage
├── process.py      Build stage
├── migrate.py      Flat-to-hierarchical raw data migration utilities
└── publish.py      Publish stage
```

Raw observations live at `data/fuel/{region}/{subregion}/{country}/{source}/observations.csv`.

`source` is the YAML filename stem. `source_key` remains row/state metadata and does not determine directory names.

## Current Production Code

The working fuel pipeline lives at `src/cpi/fuel_prices/` with its own
module CLI. See `src/cpi/fuel_prices/README.md`.
