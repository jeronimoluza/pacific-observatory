# src/configs/

Cross-pipeline configuration files. Every pipeline reads from here
for region/country metadata and shared settings.

## Files

| File | Purpose |
|------|---------|
| `regions.yaml` | Regions and countries: slug, name, ISO3, currency, grouped by region |
| `settings.yaml` | Data dirs, output dirs, ancillary data paths |

## How These Are Used

- `core.config.load_regions()` reads `regions.yaml` → region-level data
- `core.config.load_countries()` flattens `regions.yaml` → all countries across regions
- `core.config.countries_for_region("pacific")` → list of country slugs in a region
- `core.config.load_settings()` reads `settings.yaml`
- Pipeline configs (`fuel/configs/`, `text/configs/`) reference country
  slugs defined in `regions.yaml`

## Adding a Country

1. Add entry under the appropriate region in `regions.yaml`
2. Create pipeline-specific configs as needed

## Adding a Region

1. Add top-level entry to `regions.yaml` with name, description, countries
2. Run `po init --region <name>` to scaffold pipeline directories
