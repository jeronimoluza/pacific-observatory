# Fuel Prices

`src/cpi/fuel_prices/` is the fuel branch of `price_atlas`. It collects source observations, stores them as per-source `observations.csv` files, applies lightweight normalization fixes, and publishes fuel-facing HTML artifacts.

## Stage Map

- `collect` - fetch source updates, backfill FuelCheck history, and capture news evidence sidecars.
- `normalize` - apply targeted cleanup fixes to the legacy consolidated CSVs where needed.
- `publish` - regenerate `fuel_prices.html` and `fuel_policy_overview.html` from current data.

## Worktree Target

- `ARCHITECTURE.md` and `stages.py` define the worktree target: `collect -> reconstruct -> normalize -> enrich`.
- `reconstruct/` now owns the merged legacy-plus-observations assembly that used to live only in `loader.py`.
- `normalize/` now owns the repeatable publish-time cleanup and dedupe rules that used to be embedded in `loader.py`.
- The public CLI remains `update/fetch`, `normalize`, and `publish` while the staged architecture is migrated source by source.

## CLI Shape

The internal module CLI now follows the same stage language as the shared docs:

```bash
poetry run python -m src.cpi.fuel_prices collect --source kr_opinet_daily_avg
poetry run python -m src.cpi.fuel_prices reconstruct
poetry run python -m src.cpi.fuel_prices compare-reconstruct
poetry run python -m src.cpi.fuel_prices update
poetry run python -m src.cpi.fuel_prices update --source au_aip_tgp_weekly
poetry run python -m src.cpi.fuel_prices normalize
poetry run python -m src.cpi.fuel_prices publish --target all
poetry run python -m src.cpi.fuel_prices backfill-fuelcheck --overwrite
python -m src.cpi.fuel_prices.gen_sources_html
python -m src.cpi.fuel_prices.gen_sources_excel
```

Backward-compatible aliases still exist:

- `fetch` -> `update`
- `migrate` -> `normalize`
- `visualize` -> `publish --target prices`
- `policy` -> `publish --target policy`
- `tracka-news` -> `news-evidence-th`
- `tracka-news-kr` -> `news-evidence-kr`

## Key Outputs

- `data/cpi/fuel_prices/<country>/<source_key>/observations.csv` - canonical per-source storage.
- `data/cpi/fuel_prices/snapshots/gpp_daily_snapshot_<date>.csv` - GlobalPetrolPrices daily snapshot imports used for reconstruction comparisons.
- `data/cpi/fuel_prices_staged/reconstruct/fuel_observations.csv` - staged reconstructed retail fuel table.
- `data/cpi/fuel_prices_staged/reconstruct/commodity_observations.csv` - staged reconstructed commodity table.
- `data/cpi/fuel_prices_staged/compare/reconstruct_vs_baseline.md` - staged comparison report against the local baseline tables.
- `data/cpi/fuel_prices/fuel_prices.html` - fuel price visualization.
- `data/cpi/fuel_prices/fuel_policy_overview.html` - policy summary visualization.
- `data/cpi/fuel_prices/data_sources.html` - browseable HTML source catalog from fetcher metadata plus source stats.
- `data/cpi/fuel_prices/fuel_source_inventory.xlsx` - observed-source Excel inventory keyed by raw `retail_series_enriched.csv` `source_key` values.
- `data/cpi/published/news_evidence/fuel_prices/` - published news-evidence sidecars.

## Code Layout

- `fetchers/` - source-specific collection logic.
- `collect/` - reusable collection-stage pipeline helpers and staged collect paths.
- `commands/` - stage-oriented CLI handlers.
- `reconstruct/` - explicit reconstruction-stage loading and baseline merge helpers.
- `normalize/` - repeatable retail-series cleanup helpers for publish-ready data.
- `stages.py` - target stage contracts and staged output path helpers.
- `backfill_fuelcheck.py` and `fuelcheck_resources.py` - FuelCheck historical backfill workflow.
- `loader.py`, `storage.py`, `csv_store.py` - canonical loading and persistence helpers.
- `visualize.py`, `visualize_policy.py` - publish artifacts.
- `gen_sources_html.py` - data-source catalog generation.
- `gen_sources_excel.py`, `source_inventory.py` - observed-source Excel export and shared source-inventory helpers.

## Notes

- Per-source storage is the long-term canonical layout.
- The legacy consolidated CSVs still exist, so `normalize` is currently a lightweight cleanup stage rather than a full rebuild.
- The staged worktree keeps baseline outputs under `data/cpi/fuel_prices/` and targets new migration artifacts under `data/cpi/fuel_prices_staged/`.
- `gen_sources_html.py` inventories fetcher metadata and freshness-style stats, while `gen_sources_excel.py` exports one row per observed raw `source_key` from `data/cpi/fuel_prices_staged/enrich/retail_series_enriched.csv`.
- `Track A` is legacy wording; user-facing docs and commands now refer to `news evidence` instead.
- Many older fetcher and visualization modules are still larger than the new 500-line target; treat that limit as the direction for touched files and future refactors.
