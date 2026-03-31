# src/ancillary_data/

Loaders for reference datasets used across pipelines: World Bank
indicators, IMF data, and other external sources.

## Modules

| Module | Datasets | Used by |
|--------|----------|---------|
| `worldbank.py` | GDP per capita, population, subsidies | Fuel (enrichment) |
| `imf.py` | CPI validation, subsidy estimates | Prices (CPI comparison) |

## Data Location

Ancillary data files live at `data/ancillary_data/` (configured in
`src/configs/settings.yaml`). These are reference datasets that
change infrequently and are shared across pipelines.

```
data/ancillary_data/
├── worldbank/
│   ├── gdp_per_capita.csv
│   ├── population.csv
│   └── subsidies.csv
└── imf/
    ├── subsidies.xlsb
    └── subsidies.xlsx
```
