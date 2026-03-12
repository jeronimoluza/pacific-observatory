# Fuel Prices

`src/cpi/fuel_prices/` is the fuel branch of `price_atlas`. It collects source observations, stores them as per-source `observations.csv` files, applies lightweight normalization fixes, and publishes fuel-facing HTML artifacts.

## Stage Map

- `collect` - fetch source updates, backfill FuelCheck history, and capture Track A news evidence.
- `normalize` - apply targeted cleanup fixes to the legacy consolidated CSVs where needed.
- `publish` - regenerate `fuel_prices.html` and `fuel_policy_overview.html` from current data.

## CLI Shape

The internal module CLI now follows the same stage language as the shared docs:

```bash
python -m src.cpi.fuel_prices update
python -m src.cpi.fuel_prices update --source au_aip_tgp_weekly
python -m src.cpi.fuel_prices normalize
python -m src.cpi.fuel_prices publish --target all
python -m src.cpi.fuel_prices backfill-fuelcheck --overwrite
```

Backward-compatible aliases still exist:

- `fetch` -> `update`
- `migrate` -> `normalize`
- `visualize` -> `publish --target prices`
- `policy` -> `publish --target policy`

## Key Outputs

- `data/cpi/fuel_prices/<country>/<source_key>/observations.csv` - canonical per-source storage.
- `data/cpi/fuel_prices/fuel_prices.html` - fuel price visualization.
- `data/cpi/fuel_prices/fuel_policy_overview.html` - policy summary visualization.
- `data/cpi/published/track_a/fuel_prices/` - Track A shadow artifacts for news evidence.

## Code Layout

- `fetchers/` - source-specific collection logic.
- `commands/` - stage-oriented CLI handlers.
- `backfill_fuelcheck.py` and `fuelcheck_resources.py` - FuelCheck historical backfill workflow.
- `loader.py`, `storage.py`, `csv_store.py` - canonical loading and persistence helpers.
- `visualize.py`, `visualize_policy.py` - publish artifacts.
- `gen_sources_html.py` - data-source catalog generation.

## Notes

- Per-source storage is the long-term canonical layout.
- The legacy consolidated CSVs still exist, so `normalize` is currently a lightweight cleanup stage rather than a full rebuild.
- Many older fetcher and visualization modules are still larger than the new 500-line target; treat that limit as the direction for touched files and future refactors.
