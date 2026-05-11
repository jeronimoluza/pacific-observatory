# How to Add a New Fuel Price Fetcher

This guide covers the migrated `src/fuel/` pipeline.

Canonical topology:

```text
src/fuel/configs/{region}/{subregion}/{country}/{source}.yaml
src/fuel/fetchers/{region}/{subregion}/{country}/{source}.py
data/fuel/{region}/{subregion}/{country}/{source}/observations.csv
```

`source` is the YAML filename stem. `source_key` stays inside the YAML and output rows as dataset metadata, but it is not the directory name.

## Quick Start

1. Create a source YAML at `src/fuel/configs/{region}/{subregion}/{country}/{source}.yaml`
2. Create a canonical wrapper module at `src/fuel/fetchers/{region}/{subregion}/{country}/{source}.py`
3. Point the YAML `module:` field at the wrapper path relative to `fuel.fetchers`
4. Run `python run.py fuel collect --source {source_key} --dry-run`
5. Run `python run.py fuel collect --source {source_key}`

## Step 1: Add The Country If Needed

If the country does not exist in `src/configs/countries.yaml`, add it there and add the country slug to the correct subregion in `src/configs/regions.yaml`.

## Step 2: Create The YAML Config

Copy the template:

```bash
cp src/fuel/configs/_examples/country_template.yaml \
   src/fuel/configs/{region}/{subregion}/{country}/{source}.yaml
```

Example shape:

```yaml
source_key: qe_qa_monthly
module: menaap.gulf_states.qatar.qatar_energy
function: fetch_qa_qatarenergy
url: https://example.gov/fuel-prices
fallback_date: 2025-01-01
priority: 10
cadence: monthly
carry_forward: true

products:
  "Gasoline Premium":
    series_key: gasoline_premium_91
    fuel_family: gasoline
    unit: liter
    include_in_build: true
    grade: premium
    octane_ron: 91
```

Notes:

- One YAML file represents one source.
- `module:` is the canonical wrapper module path relative to `fuel.fetchers`.
- `source` is implied by the filename stem and should match the wrapper filename.
- `source_key` is still required in rows and state, but it does not drive storage paths.

## Step 3: Create The Wrapper Module

Create the canonical wrapper:

```bash
cp src/fuel/fetchers/_examples/fetcher_template.py \
   src/fuel/fetchers/{region}/{subregion}/{country}/{source}.py
```

For source-specific logic, implement directly in the wrapper.

For shared providers, keep the wrapper thin and delegate to internal helpers under `src/fuel/fetchers/_shared/`.

Example wrapper:

```python
from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_jo

__all__ = ["fetch_tfp_jo"]
```

## Fetcher Contract

```python
def fetch_source_name(cutoff: date) -> pd.DataFrame | None:
```

- Input: `cutoff`, the newest stored observation date for that source
- Return only rows with `observation_date > cutoff`
- Return `None` or an empty DataFrame when there is no new data
- Do not write files directly; collection handles deduplication and storage

Expected row columns:

| Column | Required | Description |
| --- | --- | --- |
| `observation_date` | Yes | ISO date string (`YYYY-MM-DD`) |
| `country` | Yes | Country display name |
| `fuel_product` | Yes | Raw product name from the source |
| `price_local` | Yes | Numeric local-currency price |
| `currency` | Yes | ISO currency code |
| `source_key` | Yes | Dataset identifier from the YAML |
| `unit` | No | Defaults to liter if omitted |
| `subnational_area` | No | State or province |
| `city` | No | City |
| `address` | No | Station or address |

## Step 4: Test

```bash
# Preview without writing
python run.py fuel collect --source qe_qa_monthly --dry-run

# Run the source
python run.py fuel collect --source qe_qa_monthly

# Verify canonical storage
python run.py fuel build --country qatar
```

Canonical raw observations will be written to:

```text
data/fuel/{region}/{subregion}/{country}/{source}/observations.csv
```

Example:

```text
data/fuel/menaap/gulf_states/qatar/qatar_energy/observations.csv
```

## Step 5: Update Tests And Docs

Update any tests, examples, or docs to import the canonical wrapper path and to refer to the canonical `{region}/{subregion}/{country}/{source}` storage layout.

## Tips

- Use `core.http.make_session()` for HTTP requests
- Call `response.raise_for_status()` after requests
- Keep shared logic in `_shared/` only when multiple wrappers need it
- Keep wrapper files minimal when delegating to shared helpers
- Use the YAML filename stem as the canonical source name everywhere paths are involved

## Reference

- Config template: `src/fuel/configs/_examples/country_template.yaml`
- Canonical wrapper examples: `src/fuel/fetchers/menaap/**`
- Shared helper examples: `src/fuel/fetchers/_shared/`
