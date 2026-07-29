# src/text/configs/

Newspaper scraper YAML configurations, organized by region and country.

## Structure

```
configs/
├── pacific/                 Pacific region
│   ├── fiji/                Per-country directories
│   │   ├── fiji_sun.yaml
│   │   └── fiji_times.yaml
│   ├── australia/
│   └── ... (29 countries)
├── eca/                     Europe and Central Asia
│   └── ukraine/
│       ├── kyiv_independent.yaml
│       └── ...
└── _examples/
    └── newspaper_template.yaml
```

## Adding a Newspaper

1. Copy `_examples/newspaper_template.yaml` to `{region}/{country}/{newspaper}.yaml`
2. Fill in selectors and listing config
3. Test: `po text collect --source {newspaper} --dry-run`

See [HOW_TO_ADD_NEW_SCRAPER.md](../HOW_TO_ADD_NEW_SCRAPER.md)

## Discovery

`core.config.discover_pipeline_configs()` walks this directory.
Directories starting with `_` are skipped. Filter with `--region`
or `--country` at the CLI.
