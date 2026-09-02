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

## Archive fields — `archive_prefix` and `archive_path_re`

These two fields are what makes a source retrievable from **Common Crawl**, which
is how the pipeline recovers historical price series that predate our own
scraping. A live spider gives you today forward; CC gives you 2013 onward. Set
them at onboarding — a source added without them is invisible to the CC resolver
and nobody finds out.

Both are read by `src/prices/price_scraping/archive/cc_index.py`.

### The one rule that matters: `archive_prefix` is the bare registrable host

```yaml
archive_prefix: "banjoosuperstore.com/"      # correct
archive_prefix: "banjoosuperstore.com/product/"   # WRONG — silently caps recall
```

`archive_prefix` is a plain **string** prefix applied to cdx index lines
(`cc_index.py:351`, `line.startswith(surt_prefix(archive_prefix))`) **before**
`archive_path_re` is ever consulted. A path segment in the prefix is therefore a
hard ceiling on what any regex can subsequently see.

When it is wrong, it fails **silently** — no manifest, no miss record, no error,
no zero-row warning. The source simply never appears in a resolve pass. A
2026-09-02 audit found **261 of 882 sources** in exactly this state. Dropping
`fravega_ar` from `/p/` to the bare host took it from **0 rows to 40,346 spanning
2014-2025**; it could never reach its real `/{category}/p` product family.

Optimise for **recall, not scan time**. Over-inclusion costs almost nothing:

- The cap is looser than "path prefix" suggests. `surt_prefix()` does
  `path.rstrip("/")`, so `www.fravega.com/p/` becomes the bare string
  `com,fravega)/p` — which also matches `/panasonic`, `/pampers` and
  `/philips`. It was never the precise filter it looks like.
- `archive_path_re` does the real filtering afterwards, on every candidate.

**The asymmetry is the whole argument.** Over-inclusion costs *scan time*.
Under-inclusion loses *data*, silently, with nothing in any log to say so. Those
are not comparable costs, which is why the answer is always the bare host and not
"a carefully chosen prefix."

And a bare host is the only form that **survives a URL-scheme migration**.
`sheridans_ie` broke when the site moved WooCommerce → Shopify and `/product/`
became `/products/`. `tmpnp_zw`'s own canonical URLs said `/products/` while CC
had only ever archived `/shop/...`. A path prefix cannot survive either; a bare
host is immune to both.

### `www.` does not matter — but subdomains do

`surt_prefix()` mirrors CC's SURT canonicalisation and strips a leading `www.`:

```python
host = host.lower()
if host.startswith("www."):
    host = host[4:]
```

So `www.alvaro.fo/` and `alvaro.fo/` produce the identical key `fo,alvaro)/`. A
site that 308-redirects bare → www is a non-issue: CC indexes the URL it fetched
and both canonicalise the same way.

**Only `www.` is stripped.** A catalog on any other subdomain —
`shop.example.com`, `gcc.luluhypermarket.com` — is a *different* SURT key and
must be written out in full.

### Three ways `archive_path_re` silently never fires

1. **A query string in the pattern — a structural impossibility, not a near
   miss.** The regex is `re.search`ed against `urlparse(url).path`
   (`cc_index.py:366`). The query is *absent from the string being matched*, so
   a pattern containing `?` or `&` cannot fire under any circumstances. A site
   that keys products off `?category=` (e.g. `superselectos_sv`) is unfixable
   through this mechanism — record that; don't ship a pattern that cannot fire.
2. **Case — the prefix is case-insensitive and the regex is case-sensitive.**
   This asymmetry is the actual trap. `surt_prefix` lowercases the prefix
   *including its path* (itself a fix: `shop.cosmed.com.tw/SalePage/` matched
   nothing until the path was lowercased), but `archive_path_re` is matched
   against the **raw** path, which is never lowercased. `cozmo_jo` broke solely
   because its regex demanded lowercase while the site serves
   `/cozmostore/Categories/.../p/<id>`. A prefix that works is no evidence at
   all that a same-cased regex will.
3. **Over-tight depth anchoring.** `re.search` is unanchored at the right, so
   depth is free. `libdelivery_lr` serves four-segment PDPs
   (`/item/restaurants/oportos/breakfast/omelette-ham-cheese/`) and a plain
   `^/item/` matches all of them. Prefer loose.

### Derive the pattern from what CC holds, not from the live site

This is the single most common source of a bad pattern. Nearly every one of the
261 broken prefixes came from reading the live site's URL shape and assuming CC
matched it. The live site is today's scheme; CC is every scheme the site ever
had. `djor_fo` shipped `^/product/[^/?]+` — correct against the live site,
verified against 2,159 freshly scraped rows — and matched **6 of 267** archived
records.

The failure is live, not historical: `comoresenligne_km` was onboarded in a
separate session within the same hour as this section was written, and has
**725 captures with zero reachable**, because its prefix carries a `/fr/` locale
segment and a `/product/` segment that both exist on the live site and appear
nowhere in the archive. Two independent authors, same hour, same mistake. Read
the archive first.

Where a live-site pattern and the archived paths disagree, do not widen the regex
on a guess. Two very different situations produce the same symptom and need
opposite fixes:

| Symptom | Diagnosis | Fix |
|---|---|---|
| Archived paths use a *different product base* with per-product slugs | Site migrated its permalink scheme | Widen the regex to cover both bases |
| Archived paths are only the homepage and a bare/paginated listing | CC never crawled the PDPs | No regex helps — record it and move on |

Telling them apart needs the distinct archived paths, not the counts. Widening a
regex for case 2 sends fetches after listing pages forever.

### `spider` is mandatory for CC, including for sources you think don't need it

`cc_config.py:147` reads:

```python
if not (cfg.spider and cfg.archive_prefix):
    continue
```

A manifest carrying `source_key` and `archive_prefix` but **no `spider`** is
skipped outright — again with no error. 402 of the 608 prefix-less configs in the
tree are fetcher-scaffolded and hit precisely this.

### Recording crawl-era coverage: presence yes, absence no

Record positive facts — "first seen CC-MAIN-2019-04, 936 records across 8
crawls". Do **not** record an absence unless you probed deep (`max_blocks=40`+)
across several crawls.

Shallow probes manufacture false absences. The cdx index is SURT-sorted, so
`/about`, `/blog`, `/images` and `/robots.txt` can consume the entire block
budget before the first `/product...` line is reached.
`pharmacie_saintemarie_ga` read **0 records at 5 blocks and 38 of 38 at 40**.
Crawl recency cuts both ways too: CC-MAIN-2026-25 surfaced content that
CC-MAIN-2024-46 missed entirely for four sources.

### Record the platform fingerprint — it predicts parse yield

Parse coverage, not index coverage, is the real bottleneck. The archive fetch
ships four generic tiers: JSON-LD, OpenGraph meta, Next.js flight data, and
inline microdata. **JSON-LD yield is ~0% pre-2016 and rises to ~46% by 2026**, so
a source whose value is its 2019-2020 tail will lean on the microdata tier
instead.

Note the platform (WooCommerce / Shopify / Magento / VTEX / PrestaShop) and the
extraction route in the inventory so that yield can be predicted rather than
discovered after a scan. There is no `platform:` field on `PriceSourceConfig`
today, and the model is `extra="forbid"` — adding one to a manifest without
adding it to the model raises at load time and takes down the **global**
`prices collect --list`, not just that source. Put it in the inventory prose
unless and until the field is added to the model.
