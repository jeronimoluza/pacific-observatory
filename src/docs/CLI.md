# Production CLI

This file describes the production-facing `po` surface we want humans to learn first. It is organized by domain and pipeline stage rather than by internal Python module names.

Use this file for the shared command map. Use local READMEs and local docs for implementation details, advanced flags, and module-specific caveats.

## Design Rules

- Prefer domain names people recognize: `text`, `price_atlas`, `tourism`.
- Prefer stage verbs people can remember: `health`, `collect`, `normalize`, `enrich`, `analyze`, `publish`, `update`.
- Keep `health` cheap and safe.
- Keep deep operational flags close to the local area that owns them.

## Main Commands

| Command | Purpose | Go deeper |
| --- | --- | --- |
| `po text health` | Quick confidence check for text configs, storage, and recent runs. | `src/text/README.md`, `src/text/docs/` |
| `po text collect <newspaper>` | Collect or update articles for one newspaper or a country batch. | `src/text/README.md`, `src/text/scrapers/orchestration/README.md` |
| `po text analyze` | Rebuild text-derived measures and text analysis outputs. | `src/text/README.md` |
| `po price_atlas update` | Refresh the latest raw price and fuel inputs from active sources. | `src/cpi/README.md`, `src/cpi/price_scraping/README.md`, `src/cpi/fuel_prices/README.md` |
| `po price_atlas normalize` | Rebuild or clean the canonical price tables used by downstream enrichment and analysis. | `src/cpi/README.md`, `src/cpi/fuel_prices/README.md` |
| `po price_atlas enrich` | Add quantities, COICOP, quality flags, and other derived price fields. | `src/cpi/coicopping/README.md` |
| `po price_atlas analyze` | Build indices, comparison outputs, and analytical tables. | `src/cpi/price_index/README.md`, `src/cpi/analysis/` |
| `po price_atlas publish` | Regenerate publishable dashboards, tables, and other outward-facing artifacts. | `src/cpi/fuel_prices/README.md`, `src/cpi/visualization/README.md` |
| `po tourism collect` | Refresh tourism source pulls. | `src/tourism/scrapers/`, `src/tourism/apis/` |
| `po tourism analyze` | Rebuild tourism-facing analytical outputs. | `src/tourism/analysis/`, `src/tourism/plotting/` |

## About `update`

`update` is the default human command when the goal is "bring this area current." Under the hood it may call `collect`, `normalize`, or other lightweight stage transitions, but the public surface should stay simple.

## Shared Working Rule

If a command grows enough flags or caveats that it stops being memorable, keep the shared `po` name small and move the detailed behavior into the local docs that own the workflow.
