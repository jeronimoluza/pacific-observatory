# YAML manifest schema

The manifest sits at `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` (per-country) or `src/prices/configs/_global/<source>.yaml` (truly global aggregate series). Path-derived fields (region, subregion, country, source) **must not appear in the body** — the loader extracts them from the path; duplicating them breaks discovery.

## Body fields

| Field | Required | Notes |
|---|---|---|
| `scaffolding` | yes | `spider` or `fetcher` |
| `extraction_pattern` | yes | One of `scrapy_html`, `scrapy_api`, `scrapy_playwright`, `scrapy_listing`, `rest_api`, `tabular_download`, `pdf`, `html_scrape` |
| `analytical_role` | yes | One of `retailer_sku`, `official_avg`, `tariff`, `cpi_benchmark`, `aggregate_proxy` |
| `coicop_classification` | yes | One of `classifier`, `source_curated`, `publisher_labeled` |
| `channel` | **yes — the key must be present even when the value is `null`** | From the `Channel` enum in `src/prices/enrich/schemas.py`. `null` for non-retail sources. An out-of-enum value *or* an omitted key breaks global `prices collect --list`, not just this source. |
| `coicop_codes` | conditional | Required when `coicop_classification ∈ {source_curated, publisher_labeled}`. List of codes the source's rows carry (e.g. `["07.2.2", "04.5.4"]` for fuel). Absent for `classifier`. |
| `source_key` | yes for `fetcher` | Stable identifier; matches the fetcher function name (`fetch_<source_key>`) |
| `spider` | yes for `spider` | The Scrapy spider's `name` attribute |
| `module` | yes for `fetcher` | Dotted path under `src/prices/fetchers/`, package prefix omitted — `eap.southeast_asia.indonesia.pertamina`, `_shared.eap.shopee`, `_global.wb_pink_sheet` |
| `function` | yes for `fetcher` | Name of the public callable inside `module` |
| `url` | yes | Canonical landing page or API endpoint |
| `language` | yes | ISO 639-1 code of the site's primary listing/page language |
| `cadence` | yes | `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `irregular` |
| `fallback_date` | yes for `fetcher` | Earliest date the fetcher can backfill to (ISO). Used as the cutoff on first run, so set it back far enough that run 1 returns real history. |
| `notes` | no | Free-form maintainer note — anything non-obvious |
| `active` | no | `false` only when intentionally disabled |

Fields explicitly **not** in the schema: `source_type` (the old A–F letters), `priority` (PPP wants all sources, not a ranking), `observation_level` (subsumed by `analytical_role`), `coicop_divisions` (replaced by `coicop_codes`).

## Examples

Country-bound fetcher (Pertamina Indonesia, fuel):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["07.2.2", "04.5.4"]
channel: null
source_key: id_pertamina
module: eap.southeast_asia.indonesia.pertamina
function: fetch_id_pertamina
url: https://mypertamina.id/fuels-harga
language: id
cadence: monthly
fallback_date: 2020-01-01
notes: |
  Schedule-1 retail prices only. _COICOP_MAP keyed by product name
  (Pertalite/Pertamax/etc. → 07.2.2; Minyak Tanah → 04.5.4).
```

Spider (FairPrice Singapore, retailer SKU):

```yaml
scaffolding: spider
extraction_pattern: scrapy_api
analytical_role: retailer_sku
coicop_classification: classifier
channel: supermarket
spider: fairprice
url: https://www.fairprice.com.sg
language: en
cadence: daily
```

Wholesale market feed (general catalog walker, `official_avg`):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: official_avg
coicop_classification: classifier
channel: wholesale
source_key: th_talaadthai
module: eap.southeast_asia.thailand.talaadthai
function: fetch_th_talaadthai
url: https://talaadthai.com
language: th
cadence: daily
fallback_date: 2024-01-01
notes: |
  Whole-catalog numeric-id walk (~2,000 commodities), not a targeted
  extractor. Emits current + prev daily snapshot as the midpoint of the
  published min/max. Unit passthrough incl. Thai units.
```

CPI benchmark (BPS Indonesia):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: cpi_benchmark
coicop_classification: publisher_labeled
coicop_codes: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
channel: null
source_key: id_bps_cpi
module: eap.southeast_asia.indonesia.bps_cpi
function: fetch_id_bps_cpi
url: https://www.bps.go.id/en/statistics-table/...
language: en
cadence: monthly
fallback_date: 2018-01-01
notes: |
  COICOP 2018 13-division grouping (publisher publishes 12; division
  13 is folded into 12 by BPS). Translation map: Bahasa → COICOP codes.
```

Marketplace — third-party sellers (Shopee in Singapore, thin per-country wrapper):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: retailer_sku
coicop_classification: classifier
channel: marketplace
source_key: sg_shopee
module: eap.southeast_asia.singapore.shopee
function: fetch_sg_shopee
url: https://shopee.sg
language: en
cadence: daily
fallback_date: 2024-01-01
```

Platforms selling through **third-party sellers** (Shopee, Lazada, Rakuten,
Yahoo Shopping) are marketplaces — long-tail catalogs with seller-authored
product names. The authoritative value list, with a discriminating test for
each, is the `channel` entry in `src/prices/docs/GLOSSARY.md`.

Truly global aggregate (World Bank Pink Sheet, at `configs/_global/wb_pink_sheet.yaml`):

```yaml
scaffolding: fetcher
extraction_pattern: tabular_download
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["01", "04", "07"]
channel: null
source_key: wb_pink_sheet
module: _global.wb_pink_sheet
function: fetch_wb_pink_sheet
url: https://www.worldbank.org/en/research/commodity-markets
language: en
cadence: monthly
fallback_date: 1960-01-01
notes: |
  Emits aggregate-region rows (country="Global"). Reference series
  for commodity-price benchmarking across all countries.
```
