# src/configs/

Cross-pipeline configuration files. Every pipeline reads from here
for region/country metadata and shared settings.

## Files

| File | Purpose |
|------|---------|
| `regions.yaml` | Topology tree: region → subregion → country slugs, with names at region/subregion levels |
| `countries.yaml` | Flat properties: name, iso3, currency, languages per country slug |
| `settings.yaml` | Data dirs, output dirs, ancillary data paths |

## How These Are Used

- `core.config.load_regions()` reads `regions.yaml` → topology tree
- `core.config.load_countries()` reads `countries.yaml` → flat country properties
- `core.config.get_label(slug)` → display name for any region, subregion, or country
- `core.config.get_country_path(slug)` → `(region, subregion, country)` tuple
- `core.config.countries_for_region("eap")` → all country slugs in EAP
- `core.config.countries_for_subregion("eap", "pacific_islands")` → country slugs in subregion
- `core.config.resolve_subregion_region("pacific_islands")` → `"eap"`
- `core.config.discover_pipeline_configs(dir, region, subregion, country)` → YAML paths

## Adding a Country

1. Add slug to the appropriate subregion's `countries` list in `regions.yaml`
2. Add properties entry in `countries.yaml` (name, iso3, currency, languages)
3. Create pipeline-specific configs as needed

## Adding a Region or Subregion

1. Add to `regions.yaml` with `name` and structure
2. Run `po init --region <name>` to scaffold pipeline directories
