# src/fuel/configs/

YAML source configuration files for the fuel pipeline, organized
by region and country.

## Layout

```
configs/
├── pacific/                  Pacific region
│   ├── australia.yaml        Each file defines products + sources for a country
│   ├── fiji.yaml
│   └── ...
├── _examples/
│   └── country_template.yaml Annotated template — start here
└── README.md
```

## Config Schema

Each YAML file defines:
- `country`, `iso3`, `currency` — country metadata
- `products` — fuel types tracked (diesel, gasoline, LPG, etc.)
- `sources` — data sources, each mapping to a fetcher function

See `_examples/country_template.yaml` for annotated reference.
Full schema: [docs/fuel/YAML_CONFIG_REFERENCE.md](../../../docs/fuel/YAML_CONFIG_REFERENCE.md)

## Discovery

`core.config.discover_pipeline_configs()` recursively finds all
`*.yaml` files in this directory, skipping anything under `_examples/`.
Filter by `--region` or `--country` at the CLI.
