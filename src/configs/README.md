# src/configs/

Cross-pipeline configuration files. Every pipeline reads from here
for country metadata, region definitions, and shared settings.

## Files

| File | Purpose |
|------|---------|
| `countries.yaml` | Country registry: slug, name, ISO3, region, currency |
| `regions.yaml` | Region → country list mappings, used by CLI `--region` filter |
| `settings.yaml` | Data dirs, output dirs, ancillary data paths |

## How These Are Used

- `core.config.load_countries()` reads `countries.yaml`
- `core.config.load_regions()` reads `regions.yaml`
- `core.config.load_settings()` reads `settings.yaml`
- Pipeline configs (`fuel/configs/`, `text/configs/`) reference country
  slugs defined in `countries.yaml`

## Adding a Country

1. Add entry to `countries.yaml` (slug, name, iso3, region, currency)
2. Add slug to the region list in `regions.yaml`
3. Create pipeline-specific configs as needed

## Adding a Region

1. Add entry to `regions.yaml`
2. Run `po init --region <name>` to scaffold pipeline directories
3. Add countries to `countries.yaml` with the new region
