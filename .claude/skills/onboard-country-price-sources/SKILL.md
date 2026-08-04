---
name: onboard-country-price-sources
description: "Discover, scaffold, and end-to-end-test new price-data sources for ONE country of the `prices` pipeline, targeting full COICOP 2018 basket coverage for PPP / Real-Exchange-Rate analysis. Use this skill whenever the user wants to expand price-source coverage for a single country — phrases like 'find new sources for Indonesia', 'add supermarkets in Brunei', 'cover housing/utilities in Vietnam', 'we have no sources for Korea', 'scout pharmacies in Myanmar', 'add a CPI benchmark for Fiji', or references `src/prices/configs/` and a country slug. Performs web search → three-axis source classification (scaffolding × extraction_pattern × analytical_role) → feasibility probing → spider OR fetcher scaffolding + YAML manifest under the region/subregion/country convention → automated test → per-country COICOP coverage report. For region- or subregion-wide work, the user should re-invoke once per country."
---

# Onboard Country Price Sources

Discover and onboard new price-data sources for ONE country of the `prices` pipeline. The deliverable is one or more working spider files **or** Python fetcher modules plus YAML manifests under `src/prices/configs/<region>/<subregion>/<country>/`, each verified by an end-to-end test run. The downstream consumer is a cross-country PPP / Real-Exchange-Rate pipeline, so coverage is measured against the full COICOP 2018 13-division basket — not just supermarket SKUs.

## When to use

- The user gives one country slug (or a country name you can resolve to a slug via `src/configs/regions.yaml` + `src/configs/countries.yaml`).
- They want to *add* sources, not modify existing ones — for a single named URL, prefer iterating on that source directly without this skill.
- For region- or subregion-wide expansion, run this skill once per country (the discovery and scoping work is country-specific). Don't try to bundle multiple countries in one invocation — selectors, anti-bot signatures, and start URLs are too country-specific to batch.

## Why this is a single-country skill

In practice every country has its own dominant retailers, its own CDN/WAF stack (shared infrastructure clusters by *tenant*, not by region — see `references/known_blockers.md` for examples like the Foodstuffs NZ Akamai stack or the MWG VN CONNECTION_RESET cluster), its own statistics office release format, its own regulator URL conventions, its own language for product names and category slugs, and its own conventions for product URL patterns. Batching countries forces shallow guessing; one-country runs let you actually open each PDP / PDF / Excel and verify the shape before scaffolding.

## Source classification — three orthogonal axes

Every source is classified along three axes that drive scaffolding choice, feasibility probing, and analytical handling. A fourth axis declares COICOP-tagging ownership. These four fields go into the YAML manifest (§ YAML manifest schema below).

### Axis 1 — `scaffolding` (binary)

| Value | Meaning |
|---|---|
| `spider` | Scrapy spider in `src/prices/price_scraping/spiders/`. Used for retailer SKU catalogues and real-estate / classifieds listings. |
| `fetcher` | Plain-Python module in `src/prices/fetchers/`. Used for everything else — official APIs, stats-office downloads, tariff pages, CPI publications. |

Phase 3 probes scaffolding=`spider` sources with the tier algorithm (1A HTML / 1B JSON / 2 Playwright / skip). Phase 3-fetcher probes scaffolding=`fetcher` sources by payload shape.

### Axis 2 — `extraction_pattern`

| Value | Typical sources |
|---|---|
| `scrapy_html` | Server-rendered retailer PDP HTML — Tier 1A |
| `scrapy_api` | Retailer JSON / GraphQL endpoint — Tier 1B |
| `scrapy_playwright` | SPA retailers needing JS hydration — Tier 2 |
| `scrapy_listing` | Real-estate / classifieds listing-card spiders |
| `rest_api` | Official tracker JSON endpoints (Pertamina, Opinet, PriceCatcher) |
| `tabular_download` | Stats-office CSV / XLS / Parquet downloads |
| `pdf` | Regulator orders, NSO PDF tables |
| `html_scrape` | Static HTML tariff pages, telco plan pages |

Tells the reader (and the next skill run) what shape of code lives in the module without re-opening it. Drives which recipe in `references/fetcher_pattern.md` applies.

### Axis 3 — `analytical_role`

| Value | Examples | PPP layer |
|---|---|---|
| `retailer_sku` | FairPrice SG, KlikIndomaret ID, Coupang KR | Per-SKU stickiness + basket assembly |
| `official_avg` | SingStat ARP, BPS HK-58, JP Retail Price Survey | Item-level averages for basket |
| `tariff` | SP Group SG, PLN ID, FCCC fuel, Singtel plans | Administered-price layer |
| `cpi_benchmark` | DOSM CPI, PSA CPI, SBS CPI, ABS CPI, BPS CPI | Index benchmark (NOT a fallback for missing price-level coverage) |
| `aggregate_proxy` | WB Pink Sheet, Brent/WTI, IMF FX | Commodity / FX reference series |

Replaces the old `priority` field — sources of different analytical roles are **complements**, not substitutes. The PPP analyst wants all roles populated, not a "best one wins" ranking.

### Axis 4 — `coicop_classification`

Declares who tags COICOP for the rows this source emits. Drives where the COICOP map lives.

| Value | Used for | Handler |
|---|---|---|
| `deferred_gemini` | Retailer SKU spiders, stats-office tables with long free-text item lists | `src/prices/enrich/classifier/` — the ensemble-embedding → logistic-regression head, run by `prices process --stage classify`. Predicts the COICOP **leaf** from the raw product name. (The value is named `deferred_gemini` for historical reasons; the Gemini pipeline at `src/cpi/coicopping/` it once referred to is **retired** — do not route new sources there.) |
| `source_curated` | Fuel, electricity, water, telco, real-estate, tariff schedules, restaurant aggregators — sources whose domain unambiguously determines COICOP | Fetcher module carries a `_COICOP_MAP` constant written by the skill author at onboarding |
| `publisher_labeled` | CPI publications (publisher emits its own COICOP labels) | Fetcher reads the publisher's labels; may need a translation map (e.g. Bahasa → COICOP codes) |

Rows that should carry `coicop_code` but for which the map fails MUST be dropped with a logged warning — a null `coicop_code` row that should have been populated is pollution masquerading as coverage.

## Enrichment-operational fields

The four axes above route a source through the pipeline. A *separate* set of YAML fields is read by the enrichment stage and the build. Authors MUST populate these explicitly for every new source; the skill's Phase-5 scaffolding step should not finish until all required entries below are set.

| Field | Required? | Author rule | What it drives downstream |
|---|---|---|---|
| `channel` | **required on every manifest — the key must be present even when the value is `null`** | Pick from the closed enum `Channel` in **`src/prices/enrich/schemas.py`** (that module is the authority; `configs/_examples/template.yaml` only shows one example value). Use `null` for non-retail sources where `analytical_role ∈ {cpi_benchmark, official_avg, tariff, aggregate_proxy}`. | Source-mix reporting and per-channel slicing in the build. **Gotcha:** a value outside the enum, or an omitted `channel:` key, raises at load time and takes down the *global* `prices collect --list` — not just that one source. Both have happened (a `fresh_market` value; a fetcher YAML with no `channel:`). |
| `coicop_codes` | **required for narrow sources**; omit for wide | A *narrow source* is one whose entire catalog falls under a single COICOP 3-digit class (e.g. residential rentals → `04.1`; gasoline retail → `07.2`). Declare every code the source emits — `["04.1.1"]`, `["04.1.1", "04.1.2"]`. For wide sources (supermarkets, hypermarkets, marketplaces), leave unset — the classifier assigns leaves per product. | Lets `source_curated` / `publisher_labeled` rows carry a COICOP code without going through the classifier at all; feeds the Phase-8 coverage report |
| `language` | optional, recommended | ISO 639-1 of the dominant product-name language (e.g. `ja`, `ko`, `th`, `id`). Falls back to the country's first language in `src/configs/countries.yaml`, then to `"en"`. | Tier-a structural regex variants (unit-detection patterns differ by language). Note `_resolve_lang()` returns the *effective* language, which is not always the country's official one. |

### Narrowness rule

A source is **narrow** iff `len({c[:4] for c in coicop_codes}) == 1`, where `c[:4]` is the 3-digit class prefix (e.g. `"04.1"`, `"07.2"`). `["04.1.1"]` and `["04.1.1", "04.1.2"]` are both narrow. `["07.2.2", "07.3.2"]` is wide (different classes — fuel vs transit fares are not substitutable). Narrow sources take their COICOP code straight from the manifest instead of from the classifier.

> The historical justification for this rule was that narrow sources "bypass tier-b and tier-c." That cascade was **removed on 2026-07-24** — `src/prices/enrich/tier_b/` is now empty and there is no `tier_c.py`. [ADR-0002](../../../docs/adr/0002-source-curated-short-circuit.md) and ADR-0003 describe the retired design; the rule itself survives because declaring a known COICOP code is still strictly better than asking a classifier to rediscover it.

### Worked examples

- **Residential rentals spider** (e.g. propertyguru, lamudi, ddproperty): `coicop_codes: ["04.1.1"]` → narrow → short-circuit. Tier-a still extracts pricing_basis=`monthly` and amount from `"RM 2,200 /mo"`-style strings. `sub_label_id` stays null.
- **Supermarket** (e.g. emart, coles, fairprice): leave `coicop_codes` unset. A supermarket catalog spans most of divisions 01–13; the classifier assigns a leaf per product.
- **Pharmacy chain** (e.g. watsons, boots): same — leave `coicop_codes` unset. Cache-derived codes will pick up the dominant 06.x / 13.x top-levels.
- **Fuel retailer** (e.g. shell, BP price listings, if scraped): `coicop_codes: ["07.2.2"]` → narrow → short-circuit. Same shape as rentals.
- **Cross-country aggregator** (e.g. livingcost, expatistan): `channel: aggregator`, leave `coicop_codes` unset (item breadcrumbs cover too much surface for a narrow declaration to be honest).

The fields above are independent of the four axes — a `coicop_classification: source_curated` spider source MUST still set both `channel` AND `coicop_codes`, because routing classification ≠ operational codes.

## Repo entry points

- Country topology / slug validation: `src/configs/regions.yaml`, `src/configs/countries.yaml`
- Existing price-source manifests: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` (also `src/prices/configs/_global/<source>.yaml` for truly aggregate sources)
- **Discovery inventory** (seed for Phase 2): `references/inventories/<region>/<country>.md`, with `references/inventories/<region>/_aggregators.md` for cross-country aggregators. Today only `references/inventories/eap/` is populated — other regions cold-start in Phase 2 and write back a seed at the end.
- **Slug traps** (countries whose `regions.yaml` slug doesn't match the obvious lowercase-of-name): `references/slug_traps.md`
- **Spider code** (`scaffolding: spider`): `src/prices/price_scraping/spiders/` — flat, one file per source, keyed by the spider's `name = ...` attribute
- **Centralized CSS selectors** (Tier 1A HTML spiders only): `src/prices/price_scraping/selectors.py`. API spiders and listing-card spiders bypass this and put selectors inline.
- **Fetcher code** (`scaffolding: fetcher`) — mirrors `src/fuel/fetchers/`:
  - Bucket 1 (country-bound, ~80% of fetchers): `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py`
  - Bucket 2 (regional aggregator covering multiple countries in one region): `src/prices/fetchers/_shared/<region>/<source>.py` with thin per-country wrappers at `<region>/<subregion>/<country>/<source>.py`
  - Bucket 3 (truly global aggregate, e.g. commodity benchmarks): `src/prices/fetchers/_global/<source>.py`
- **Existing COICOP classifier** (used by `coicop_classification: deferred_gemini`): `src/prices/enrich/classifier/` — ensemble embedding → logistic-regression head, run by `python run.py prices process --stage classify`
- Scrapy + Playwright settings: `src/prices/price_scraping/settings.py` (do not edit unless explicitly asked)
- CLI:
  - `python run.py prices collect --source <name> --max-items N` — runs **both** scaffoldings. `collect.py` dispatches on `scaffolding`: spiders go to Scrapy, fetchers go to `_run_fetcher()`, which resolves `module:function`, computes the cutoff from the existing CSV (falling back to `fallback_date`), and writes the columns for the source's `analytical_role`.
  - `python run.py prices collect --list` (lists everything, both scaffoldings)
  - There is **no separate `prices fetch` command** — earlier drafts of this skill said one was planned. Fetchers are collected, listed, and tested through `prices collect` like any other source.
- Data output:
  - Spiders (raw SKU items, pre-classification): `data/prices/<region>/<subregion>/<country>/<source>/raw_items/<source>_<ts>.jsonl` (one file per run)
  - Fetchers emitting PriceObservation: `data/prices/<region>/<subregion>/<country>/<source>/price_observations.csv`
  - Fetchers emitting IndexObservation: `data/prices/<region>/<subregion>/<country>/<source>/index_observations.csv`
  - Bucket 3 global: `data/prices/_global/<source>/price_observations.csv`

## Workflow

Each phase has a clear deliverable. Don't skip phases — every shortcut we've taken in the past (inventing selectors without probing, batching countries, trusting WebFetch on SPAs) has produced spiders that emit zero records.

### Phase 0 — Pre-flight checks

Before resolving the country, confirm the repo can actually support it:

1. The country slug appears in `src/configs/regions.yaml` under some `<region>.subregions.<subregion>.countries:` list.
2. The same slug has an entry in `src/configs/countries.yaml` with non-empty `currency:` and at least one `languages:` value. If either is missing or stubbed, stop and surface to the user — fetcher / spider scaffolding will silently misbehave otherwise (currency defaults to `null`, language resolution falls through to `"en"`).

### Phase 1 — Resolve country, inventory existing coverage, upgrade old manifests

1. Take the country input (slug or name) and resolve it to a canonical slug from `src/configs/regions.yaml`. **Slug traps** (where the slug doesn't match the obvious lowercase-of-name) are listed in `references/slug_traps.md` — grep there if the input is ambiguous.
2. Determine the country's subregion from `regions.yaml` — this is the path component you'll use later (e.g. `<region>/<subregion>/<country>`).
3. List **already-covered sources** for the country by reading `src/prices/configs/<region>/<subregion>/<country>/*.yaml`. Cross-check against `src/prices/price_scraping/spiders/<source>.py` (spiders are flat) and `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py` (country-bound fetchers). Also note which `_global/<source>.yaml` and `_shared/<region>/<source>.py` aggregators *cover* this country — they're "already-covered" too.
4. **Upgrade old-schema manifests in place.** Many existing YAMLs predate the four-axis schema and only have `spider: + language:` or `source_type: + coicop_divisions:`. For each old-schema YAML:
   - Look the source up by name in `references/inventories/<region>/<country>.md`
   - Backfill the four classification fields: `scaffolding`, `extraction_pattern`, `analytical_role`, `coicop_classification`
   - Backfill `coicop_codes:` (the COICOP codes this source's rows will carry — used for the Phase-8 coverage report)
   - Backfill infrastructure fields where applicable: `source_key`, `module`, `function`, `url`, `fallback_date`
   - For spider-backed sources, `scaffolding: spider`, `extraction_pattern: scrapy_*` (pick based on what the spider actually does), `analytical_role: retailer_sku`, `coicop_classification: deferred_gemini`. Keep the existing `spider:` field.
   - Remove the legacy `source_type:`, `priority:`, `observation_level:`, `coicop_divisions:` fields.
   - Write back to the same file
   - If the source isn't in the inventory, leave it untouched and record it as "unknown coverage" for the Phase 8 report
5. Read `src/configs/countries.yaml` to learn the country's `languages:` and `currency:` — these inform fetcher / spider defaults.
6. Compute the **COICOP gap set**: COICOP 2-digit divisions [01..13] minus divisions covered by the upgraded `coicop_codes:` union (taking the 2-digit prefix of each entry). Divisions in the gap set are the priority targets for this onboarding run.

### Phase 2 — Build candidate list (inventory first, fresh search only for gaps)

The starting point is **`references/inventories/<region>/<country>.md`** — a per-country, pre-verified discovery seed. Today only EAP countries have these files (split from an offline-curated source); other regions enter "cold-start mode" on the first run and the skill writes back a seed file at Phase 8.

**Warm-start path** (file exists):

1. **Read** `references/inventories/<region>/<country>.md`. Each row already has: source name, URL, COICOP divisions, source category, cadence, auth, machine-readable flag, anti-bot risk, Wayback coverage, per-SKU IDs, notes.
2. **Read** `references/inventories/<region>/_aggregators.md` if it exists. Any aggregator that lists this country (e.g. WB ICP, IMF CPI, regional marketplace aggregators) is a candidate for this country too — even though the underlying fetcher module will live under `_global/` or `_shared/<region>/`.
3. **Subtract already-covered**: remove anything from Phase 1's already-covered set.
4. **Compute the candidate list**. This is the seed.
5. **Identify gaps** that warrant a supplemental fresh search. Only trigger fresh discovery if at least one of:
   - The seed has fewer than 2 retailers with `analytical_role: retailer_sku` for the country (PPP-basket food coverage is critical and supermarkets cluster)
   - One or more COICOP divisions from Phase 1's gap set has zero candidates in the seed
   - A seed entry's URL was flagged stale ("Notes: site moved" etc.) and no replacement is given
6. **Delegate a narrow supplemental search** (general-purpose sub-agent) only for those gaps. Brief the agent with the specific gap (e.g. "find an online pharmacy in Brunei covering COICOP 06; the inventory's entry no longer resolves") rather than re-doing the full 17-category sweep. Do **not** re-list cross-country aggregators that aren't useful for PPP (Numbeo, LivingCost.org, Expatistan, MyLifeElsewhere, Nomad List) as candidates.

If no supplemental search is needed, the candidate list is just the inventory's rows. Skip straight to Phase 2.5.

**Cold-start path** (file does NOT exist — typical outside EAP):

1. Skip the inventory read.
2. Run a **full 17-category fresh search** via a general-purpose sub-agent against the 17-category table below. Brief the agent with: the country's languages and currency (from `countries.yaml`), the COICOP gap set from Phase 1, and the existing `_aggregators.md` for the region (if any). Ask for the same column shape inventory files use: source name, URL, COICOP divisions, source category, cadence, auth, machine-readable, anti-bot risk, Wayback coverage, per-SKU IDs, notes.
3. Use the agent's output as the candidate list.
4. At the end of Phase 8, **write back a new `references/inventories/<region>/<country>.md`** built from the agent's output. The next country in the same region inherits any cross-country aggregators the agent surfaced (move those to `_aggregators.md`, creating it if absent).

**Reference: 17 source categories** (the same ones that produced the inventory; consult only if briefing a supplemental search):

  | Default scaffolding | Category | Probe these |
  |---|---|---|
  | spider | Online supermarket / hypermarket / fresh-grocery | National grocery chains, hypermarkets, q-commerce |
  | spider | Online pharmacy | Pharmacy chains with browseable PDPs |
  | spider | E-commerce / marketplace | National general-merchandise sites (clothing, appliances, electronics) |
  | spider | Personal-care / beauty retailers | National drugstore-style chains |
  | spider | Streaming / app-store country pricing | Netflix, Spotify, Apple, Google country pages |
  | fetcher | Official food / commodity price tracker | Central bank or trade-ministry daily/weekly trackers |
  | fetcher | Fuel pump-price tracker | Regulator / state oil-company monthly/weekly retail fuel |
  | fetcher | National statistics office datasets | Average-price tables, retail-price surveys, household-budget-survey unit-value tables (CSV / XLS / PDF) |
  | fetcher | Customs / trade unit-value tables | Wholesale or import unit values where published |
  | fetcher | Utility tariff pages | Electricity, water, gas — regulator or operator |
  | fetcher | Telco / ISP tariff pages | Mobile and fixed-broadband plans |
  | fetcher | Public-transport fare schedules | National rail, urban transit, ferry |
  | fetcher | Airline / car / motorcycle list prices | National carrier flight prices; dealer list prices |
  | fetcher | University tuition pages | Per-program annual tuition for major national universities |
  | fetcher | Bank fee schedules / FX boards | Major retail bank fee PDFs; central bank FX tables |
  | spider | Real-estate / rental portal | Per-city rental listings with median rent by bedrooms |
  | spider | Classifieds | National classifieds covering vehicles, electronics, household |
  | fetcher | NSO CPI division indexes | Monthly/quarterly CPI by COICOP division — `analytical_role: cpi_benchmark` |

  Plus, where they cover the country: restaurant-delivery aggregators, hotel booking sites, insurance comparison sites — `scaffolding` depends on whether the price is in a paginated catalogue (spider) or in a queryable endpoint (fetcher).

Aim for 12–25 candidates across `analytical_role` values in the *combined* list (inventory + any supplemental hits, or cold-start sub-agent output). Cast wide for `retailer_sku` / `official_avg` / `tariff`; for `cpi_benchmark`, **one strong CPI source is enough** (it's the benchmark, not a coverage axis). Feasibility filtering happens in Phase 3.

If you do trigger a supplemental search, tell the sub-agent to prefer English-translated landing pages where they exist (e.g. `global.oliveyoung.com` instead of `oliveyoung.co.kr`) — they're usually easier to scrape. For CPI / NSO sources, prefer the English-language version of the stats-office portal when one exists.

### Phase 2.5 — Classify candidates along the four axes

For each candidate from Phase 2, open the URL and assign each of the four manifest classification fields:

| Confirm by looking at… | Assign to |
|---|---|
| Product detail pages with SKU IDs, add-to-cart, per-unit price | `scaffolding: spider`, `analytical_role: retailer_sku`, `coicop_classification: deferred_gemini` |
| Filterable / queryable price endpoint returning many commodities per call, often per region or per date | `scaffolding: fetcher`, `extraction_pattern: rest_api`, `analytical_role: official_avg` or `aggregate_proxy` |
| A page listing CSV / XLS / PDF downloads of national averages | `scaffolding: fetcher`, `extraction_pattern: tabular_download`, `analytical_role: official_avg`, `coicop_classification: source_curated` (if items are stable) or `deferred_gemini` (long free-text lists) |
| A static page (or PDF) listing utility / telco / transport plans with per-plan tariff | `scaffolding: fetcher`, `extraction_pattern: html_scrape` or `pdf`, `analytical_role: tariff`, `coicop_classification: source_curated` (single constant COICOP for the whole source) |
| Paginated listing of individual properties / vehicles / classifieds | `scaffolding: spider`, `extraction_pattern: scrapy_listing`, `analytical_role: retailer_sku` (listings layer), `coicop_classification: source_curated` (whole source = COICOP 04.1.1 rentals, etc.) |
| A national CPI index publication with COICOP division indexes | `scaffolding: fetcher`, `extraction_pattern: rest_api`/`tabular_download`/`pdf`, `analytical_role: cpi_benchmark`, `coicop_classification: publisher_labeled` |

If two shapes coexist on one site (e.g. an NSO publishes both CPI indexes and an average-retail-prices table), split into two YAML manifests — one with `analytical_role: cpi_benchmark`, one with `analytical_role: official_avg`. They emit different row schemas (IndexObservation vs PriceObservation) — see `references/fetcher_pattern.md`.

If a "supermarket" turns out to only show category pages with no per-product price (very common for legacy retail sites), demote to skip rather than forcing it into a spider — see `references/known_blockers.md`.

### Phase 3 — Tier classification + feasibility probing *(scaffolding=spider only)*

For each candidate, classify into one of four tiers. **Don't write selectors before classifying** — most "obvious" selectors are wrong on SPA sites because the body hasn't hydrated yet.

```
                        ┌───────────────────────────────────────┐
                        │ Tier 1A — HTML/CSS, server-rendered    │
                        │ extraction_pattern: scrapy_html       │
                        │ Build: CrawlSpider, no Playwright     │
                        └───────────────────────────────────────┘
                                       ↑ yes
curl with browser UA → does the response have h1, og: meta, AND a price visible in raw HTML?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ Tier 1B — JSON API, no auth           │
                        │ extraction_pattern: scrapy_api        │
                        │ Build: scrapy.Spider hitting the API  │
                        └───────────────────────────────────────┘
                                       ↑ yes (after API sniff)
sniff with Playwright network-capture → is there a /api/, /v1/, /v2/, /graphql endpoint
that returns ≥5KB JSON with product fields AND works with curl when only Origin/Referer
headers are set?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ Tier 2 — Playwright-rendered HTML     │
                        │ extraction_pattern: scrapy_playwright │
                        │ Build: scrapy.Spider with Playwright  │
                        │        meta + PageMethod waits        │
                        └───────────────────────────────────────┘
                                       ↑ yes
Playwright dump with 6-8s wait + scroll → are product cards present with name + price
text in the rendered HTML?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ SKIP — document the reason            │
                        │ • Cloudflare/Akamai/PerimeterX 403    │
                        │ • ERR_CONNECTION_RESET (CDN bot block)│
                        │ • Empty PDP / login wall              │
                        │ • App-only (no web catalogue)         │
                        │ • Aggregator with no per-product URLs │
                        │ • Heavy JS that doesn't hydrate at 8s │
                        └───────────────────────────────────────┘
```

Concrete probe commands and scripts live in `references/probe_patterns.md`. Pre-known blockers we already classified (so you don't waste cycles re-probing) live in `references/known_blockers.md` — **check this first** before probing.

For Tier 2 sites, the Playwright probe should also dump the HTML to `/tmp/probe_<key>_listing.html` and `/tmp/probe_<key>_pdp.html` so the selector-extraction phase has files to grep instead of re-fetching.

**When both curl and Playwright return 403 on the same site, stop.** Headless Chromium without a residential proxy and a captcha solver will not break a real Cloudflare/Akamai/Incapsula challenge. Don't iterate on it — add the site to `references/known_blockers.md` (Cloudflare / AWS WAF / Akamai section) and move on. Past attempts to push through with longer waits or stealth flags have not paid off.

### Phase 3-fetcher — Feasibility probing *(scaffolding=fetcher)*

The "tier" axis does not apply here. Instead, probe the **payload shape** so you can pick the right extractor in the fetcher:

- **`extraction_pattern: rest_api`** — hit the endpoint with `requests` + a real browser UA. Inspect JSON. Note the date / region / commodity parameters. Check whether responses paginate and whether there's an `as_of` field per row. Most failures here are: site requires a `Referer` header it doesn't document, the JSON nests prices under a `data.items[*].priceHistory[*]` shape that needs flattening, or the endpoint has a rolling window (only last 12 months — backfill via Wayback or sister "yearly" endpoint).
- **`extraction_pattern: pdf`** — `curl` the PDF, open with `pdfplumber`. If `extract_text()` returns empty, the PDF is image-only — `pytesseract` OCR fallback is acceptable but expect ~5–10× runtime. Record where the price table sits (which page, which heading). Note that regulator PDFs often have a "Schedule 1 / Retail" section + a "Schedule 2 / Bulk" or "Drum Sale" section — anchor on the retail section only, otherwise you'll mix wholesale and retail prices. **Always anchor on the LAST occurrence of "SCHEDULE 1"** — re-published orders with corrigenda leave the stale earlier table in place.
- **`extraction_pattern: tabular_download`** — download the CSV/XLS with `requests`, open with `pandas.read_csv` / `pd.read_excel`. Identify which sheet, which header row, which COICOP-division column. Stats offices love to merge cells in headers — be prepared to skip rows or read with `header=[0,1]`.
- **`extraction_pattern: html_scrape`** — many NSO and tariff pages render a price table directly in HTML. Use `pandas.read_html` first — if it parses correctly, that's the lowest-effort extractor. Otherwise BeautifulSoup with explicit selectors.
- **For tariff schedules specifically**, cadence is annual/irregular, so the fetcher runs rarely. Check whether there's an archive of prior tariffs or only the current one — if only current, the fetcher just snapshots the current value with `period_kind: effective_from` and `effective_from` = release-date.
- **For `analytical_role: cpi_benchmark`** — pick the published-machine-readable form (REST > CSV > XLS > PDF). Note whether the source publishes a single all-items index, a COICOP-1999 grouping, or the COICOP-2018 13-division grouping — the YAML's `coicop_codes:` field records what's available.

For every probe, save the raw payload sample to `/tmp/probe_<source_key>_sample.{json,csv,xlsx,pdf,html}` so you can re-read it during fetcher development without re-fetching.

**When a fetcher endpoint requires a session cookie or returns Cloudflare-protected responses**, the fetcher may still work with `requests.Session` + browser-realistic headers — but always test from a cold cache before declaring success. If it fails, document in `references/known_blockers.md` under the relevant section.

### Phase 4 — Extract real selectors *(scaffolding=spider only)*

For each non-skipped candidate, open the dumped HTML (Tier 2) or the live page (Tier 1) and identify:

- **product_name**: prefer a stable attribute like `[data-test="product_name"]` (Long Chau) or `<img>` alt text on a product card (City Mall MM). Avoid `<a>::attr(title)` as a high-priority fallback — overlay badges (e.g. "sale") frequently steal that selector. Always try `meta[property='og:title']::attr(content)` as a fallback for PDPs.
- **price**: look for a specific class like `att-product-detail-latest-price` (Co.opmart) or `data-price` attribute (Carrefour TW). On atomic-CSS sites (Sayurbox-style Twitter/RN-Web classes), there is no clean selector — extract via text regex (`Rp\s?[0-9.,]+`) instead.
- **product_id**: SKU / barcode / canonical-URL-trailing-id. Often a `meta[property='product:retailer_item_id']`, an `<input name='id'>`, or parsable from the URL.
- **category**: breadcrumb. Many sites have no inline breadcrumb on PDP — leave it null rather than invent one. A reliable breadcrumb is high-value even when it costs extra work: it's what makes a product auditable and what a human labeller reads when adjudicating a hard case.

Verification rule: **before scaffolding, every selector must have been observed matching the right text in a real dumped HTML file.** This is the single biggest determinant of whether the spider works on first run.

The three spider templates (CrawlSpider HTML, Playwright listing-card, JSON API) with full code skeletons are in `references/spider_templates.md`. Pick the one that matches the candidate's tier.

### Phase 5A — Scaffold spider + manifest *(scaffolding=spider)*

For each viable spider candidate, create three things:

1. **Spider file**: `src/prices/price_scraping/spiders/<source>.py`
   - File name and class name must be valid Python identifiers (`street11_kr.py` / `Street11KrSpider`, not `11street_kr.py`)
   - The spider's `name = "<source>"` attribute can be anything; this becomes the `--source` CLI value
   - Currency: 3-letter ISO 4217 (VND, IDR, KRW, MMK, ...) set at the spider class level. **Never** derive it from the displayed symbol — "$" is BND in Brunei, USD in Cambodia, NZD in several Pacific markets. `countries.yaml` is the *default*, not the override: when the site returns an explicit machine-readable currency code (`prices.currency_code` on Shopify/WooCommerce, a `currency` field in a JSON API), use **what the site returns**. Real cases: `tongamarket` prices in NZD and `niront` (KH) in USD, both against a different `countries.yaml` default.
   - **Minor-unit traps.** Some platform APIs return integer minor units, not decimals: WooCommerce Store API returns minor units alongside a `currency_minor_unit` exponent (divide by `10**currency_minor_unit`); Vendure `shop-api` returns **thousandths** (divide by 1000). A 100× or 1000× price error that reaches the corpus is far more damaging than a missing source — always eyeball the first extracted price against the rendered page.
2. **Selectors entry** in `src/prices/price_scraping/selectors.py` — only for `extraction_pattern: scrapy_html` spiders that use the shared `SelectorExtractor` pattern. `scrapy_api` and `scrapy_playwright` (listing-card) spiders bypass the registry and put selectors directly in the spider.
3. **YAML manifest**: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` — see "YAML manifest schema" below.

After writing all three for each candidate, run `python run.py prices collect --list` and grep for each new spider name to confirm the discovery layer picks them up. If a manifest doesn't appear, the most common cause is a wrong country slug — the loader silently drops files under unknown country directories.

### Phase 5B — Scaffold fetcher + manifest *(scaffolding=fetcher)*

For each viable fetcher candidate, decide the location bucket first.

**Bucket 1 — Country-bound** (e.g. Pertamina ID, FCCC fuel FJ, SP Group SG): one country = one source.
- Module: `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py`
- Function: `def fetch_<source_key>(cutoff: date) -> pd.DataFrame | None`
- YAML: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`

**Bucket 2 — Regional aggregator** (e.g. Shopee SEA shares API shape across SG/MY/ID/PH/TH/VN; Watsons across HK/SG/MY/TW): one shared module, per-country wrappers, per-country YAMLs.
- Shared module: `src/prices/fetchers/_shared/<region>/<source>.py`
- Wrapper per country: `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py` — re-exports the per-country callable
- YAML per country: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` — `module:` points at the wrapper

**Bucket 3 — Global aggregate series** (rare; 2–3 sources total — WTI/Brent, IMF FX, World Bank Pink Sheet): one module emits rows tagged with aggregate region labels (`country: "Global"`, `"EAP"`).
- Module: `src/prices/fetchers/_global/<source>.py`
- Function: `def fetch_<source_key>(cutoff: date) -> pd.DataFrame | None`
- YAML: **one only**, at `src/prices/configs/_global/<source>.yaml` — not per-country, because the rows are global by definition

A multi-country source that emits *per-country* rows (e.g. WB ICP publishing one row per country per ICP basket item) is **Bucket 2, not 3** — use the shared-module + per-country-wrapper pattern, so the analyst side sees a YAML under each covered country.

**The fetcher module's contract** is in `references/fetcher_pattern.md` § 1. In short: one public `fetch_<source_key>(cutoff)` function; emit `PriceObservation` or `IndexObservation` rows per `analytical_role`; idempotent skip on `observation_date <= cutoff`; `observation_hash` set last; drop unmappable COICOP rows; return `None` for no-new-data. The doc also covers helpers (optional toolbox at `src/prices/fetchers/utils.py`) and worked examples (REST API, PDF+OCR, XLS, HTML tariff, CPI).

After scaffolding, run `python run.py prices collect --list` and grep for each new `source_key` to confirm discovery — the listing shows `fetcher=<module>:<function>` for fetcher-backed sources. If a manifest doesn't appear, the usual causes are a wrong country slug or a missing `channel:` key (see the Enrichment-operational fields table). Then proceed to Phase 6.

### YAML manifest schema

The manifest sits at `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml` (per-country) or `src/prices/configs/_global/<source>.yaml` (truly global aggregate series). Path-derived fields (region, subregion, country, source) **must not appear in the body** — the loader extracts them from the path; duplicating them breaks discovery.

Body fields:

| Field | Required | Notes |
|---|---|---|
| `scaffolding` | yes | `spider` or `fetcher` |
| `extraction_pattern` | yes | One of `scrapy_html`, `scrapy_api`, `scrapy_playwright`, `scrapy_listing`, `rest_api`, `tabular_download`, `pdf`, `html_scrape` |
| `analytical_role` | yes | One of `retailer_sku`, `official_avg`, `tariff`, `cpi_benchmark`, `aggregate_proxy` |
| `coicop_classification` | yes | One of `deferred_gemini`, `source_curated`, `publisher_labeled` |
| `coicop_codes` | conditional | Required when `coicop_classification ∈ {source_curated, publisher_labeled}`. List of COICOP codes the source's rows will carry (e.g. `["07.2.2", "04.5.4"]` for a fuel fetcher; `["01..13"]` for a full-grouping CPI). Absent for `deferred_gemini`. |
| `source_key` | yes for `fetcher` | Stable identifier; matches the fetcher function name (`fetch_<source_key>`) |
| `spider` | yes for `spider` | The Scrapy spider's `name` attribute |
| `module` | yes for `fetcher` | Dotted Python path under `src/prices/fetchers/` (omit the package prefix) — e.g. `eap.southeast_asia.indonesia.pertamina` or `_shared.eap.shopee` or `_global.wb_pink_sheet` |
| `function` | yes for `fetcher` | Name of the public callable inside `module` |
| `url` | yes | Canonical landing page or API endpoint |
| `language` | yes | ISO 639-1 code of the site's primary listing/page language |
| `cadence` | yes | `daily`, `weekly`, `monthly`, `quarterly`, `annual`, or `irregular` |
| `fallback_date` | yes for `fetcher` | Earliest date the fetcher can backfill to (ISO YYYY-MM-DD). Used by the collect layer as the cutoff on first run. |
| `notes` | no | Free-form maintainer note — anything non-obvious (e.g. "Schedule 1 retail only; ignore Schedule 2 drum-sale prices") |
| `active` | no | `false` only when intentionally disabled |

Fields explicitly **not** in the v4 schema (removed from v3): `source_type` (A–F letters), `priority` (PPP wants all sources, not a ranking), `observation_level` (subsumed by `analytical_role` + schema choice), `coicop_divisions` (replaced by `coicop_codes`).

Example — country-bound fetcher (Pertamina Indonesia, fuel):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["07.2.2", "04.5.4"]
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

Example — spider (FairPrice Singapore, retailer SKU):

```yaml
scaffolding: spider
extraction_pattern: scrapy_api
analytical_role: retailer_sku
coicop_classification: deferred_gemini
spider: fairprice
url: https://www.fairprice.com.sg
language: en
cadence: daily
```

Example — CPI benchmark (BPS Indonesia):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: cpi_benchmark
coicop_classification: publisher_labeled
coicop_codes: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
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

Example — regional aggregator (Shopee in Singapore, wrapper):

```yaml
scaffolding: fetcher
extraction_pattern: rest_api
analytical_role: retailer_sku
coicop_classification: deferred_gemini
source_key: sg_shopee
module: eap.southeast_asia.singapore.shopee
function: fetch_sg_shopee
url: https://shopee.sg
language: en
cadence: daily
fallback_date: 2024-01-01
```

Example — truly global aggregate (World Bank Pink Sheet, at `configs/_global/wb_pink_sheet.yaml`):

```yaml
scaffolding: fetcher
extraction_pattern: tabular_download
analytical_role: aggregate_proxy
coicop_classification: source_curated
coicop_codes: ["01", "04", "07"]
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

### Phase 6 — Automated end-to-end test

A source is **viable** (ships as a manifest) if and only if probe passed *and* the test run returns ≥ 5 valid rows. "Valid" means: non-null `observation_date` (and `price_local` or `index_value`), correct currency, real `item_name` (or `null` where the site doesn't expose one and the schema doesn't require it). Sources that probe-pass but produce 0–4 rows fail Phase 6 and do not ship — record them in the Phase 8 skipped-sites list with the row count and a one-line hypothesis.

**`scaffolding: spider`:** run each new spider with `--max-items 5`. The CLOSESPIDER_ITEMCOUNT setting only stops the spider *after* a fetch returns more than 5 items, so a successful spider typically writes 5–40 records. Anything less means selectors or URL filters are off.

**macOS has no `timeout` builtin.** Use this pattern to cap each run:

```bash
cd /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
for src in <name1> <name2> <name3> <name4>; do
  poetry run python run.py prices collect --source $src --max-items 5 > /tmp/$src.log 2>&1 &
done
echo "Waiting up to 120s..."
sleep 120
pkill -TERM -f "run.py prices collect" 2>/dev/null
pkill -TERM -f "scrapy" 2>/dev/null
sleep 3
pkill -KILL -f "run.py prices collect" 2>/dev/null
pkill -KILL -f "chrome-headless" 2>/dev/null
wait 2>/dev/null

for src in <name1> <name2> <name3> <name4>; do
  echo "--- $src ---"
  grep -E "item_scraped_count|finish_reason|Could not extract" /tmp/$src.log | tail -5
done
```

Batch in groups of 3–4. Running too many spiders in parallel exhausts Playwright's chromium pool and they fail silently.

After the run, find the output files with `find data/prices -name "*.jsonl" | xargs ls -lt | head` and inspect the first record per spider. A successful record has:
- non-null `product_name` (matching what's on the site)
- non-null `price` (a numeric or properly-formatted string)
- correct `currency`
- a working `url`
- a real `product_id` (or `null` if the site doesn't expose one — fine)
- non-null `category` (the audit trail for downstream classification; a null here isn't fatal but makes the row much harder to adjudicate later)

**`scaffolding: fetcher`:** run each fetcher through the same `collect` command as spiders. The cutoff comes from the manifest's `fallback_date` on the first run (there's no CSV yet to read a cutoff from), so set `fallback_date` far enough back that the first run returns real history:

```bash
cd /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
for src in <source1> <source2>; do
  poetry run python run.py prices collect --source $src > /tmp/$src.fetch.log 2>&1 &
done
sleep 120
pkill -TERM -f "run.py prices collect" 2>/dev/null

for src in <source1> <source2>; do
  echo "--- $src ---"; tail -5 /tmp/$src.fetch.log
done
```

If the fetcher raises during development and you want a tighter loop than a full `collect`, import and call it directly — same contract, no persistence:

```python
import sys; sys.path.insert(0, "src")
from datetime import date
from prices.fetchers.<region>.<subregion>.<country>.<source> import fetch_<source_key>

df = fetch_<source_key>(date(2020, 1, 1))
assert df is not None and len(df) >= 5, f"only {0 if df is None else len(df)} rows"
print(f"OK: {len(df)} rows, span {df['observation_date'].min()} → {df['observation_date'].max()}")
```

The shipping gate is the `collect` run, not the direct call — only `collect` exercises the cutoff layer and the writer.

A successful fetcher writes to `data/prices/<region>/<subregion>/<country>/<source>/price_observations.csv` (or `index_observations.csv` for `analytical_role: cpi_benchmark`) and the first row should have:
- non-null `observation_date` (ISO YYYY-MM-DD)
- non-null `period_kind` (one of the enum values)
- non-null `price_local` (numeric) for PriceObservation — or non-null `index_value` for IndexObservation
- correct `currency` from `countries.yaml` (PriceObservation only)
- the right `source_key` (matches the YAML manifest)
- `coicop_code` populated when `coicop_classification ∈ {source_curated, publisher_labeled}`; absent for `deferred_gemini`
- `subnational_area` set for sources that break down sub-nationally, `null` otherwise

### Phase 7 — Iterate on failures *(scaffolding=spider)*

Common failure modes and fixes (each one we've actually hit in prior runs):

| Symptom in log / data | Cause | Fix |
|---|---|---|
| `item_scraped_count: 0`, many "Could not extract" warnings | URL filter too broad — spider is fetching non-product pages (blog, disease info, articles) | Tighten the `deny=` regex with the site's non-product path prefixes (e.g. `/bai-viet/`, `/benh/`) and/or narrow `allow=` to a 2-segment path |
| `product_name` is "sale" or other overlay-badge text | `a::attr(title)` matched a discount badge before the real product anchor | Reorder selectors: `img.product::attr(alt)` / `img::attr(alt)` before any anchor title |
| `product_name` looks like a brand/short slug instead of the full title | Card has two `<a>` elements pointing at the same PDP — image-wrap anchor came first, product-name anchor came second | Pick the anchor by selector class (e.g. `a.product-name::attr(href)`) or iterate `card.css("a")` and choose the one whose text is longer than the badge text |
| Spider takes >120s and yields zero items | Listing page hasn't hydrated within Playwright's wait window | Increase `wait_for_timeout` to 8000ms, add a second scroll pass, OR switch to API sniff (Phase 3 Tier 1B) |
| `ERR_CONNECTION_RESET` during `goto` | CDN-level bot block (MWG/Akamai/Cloudflare on origin). Real browser would also need a residential IP | **Skip this site**, document in `references/known_blockers.md` |
| HTTP 429 on API with cookie warmup | API has a dynamic security header (e.g. `x-security-key`) generated by client-side JS | Skip — reverse-engineering the key is rarely worth it |

### Phase 7-fetcher — Iterate on fetcher failures *(scaffolding=fetcher)*

| Symptom in log / data | Cause | Fix |
|---|---|---|
| Fetcher writes 0 rows, log shows "No new rows" | Cutoff is set to today and the source publishes monthly — nothing newer than cutoff exists | Re-run with a backdated cutoff (`--cutoff 2020-01-01`) once during onboarding to verify the fetcher works against historical data |
| `pdfplumber` returns empty text from a PDF | PDF is image-only (scanned) | Add the `_ocr_pdf()` helper from `references/fetcher_pattern.md`; expect ~5–10× slower runs |
| Extracted price is 10× or 100× off | Currency-display shorthand (e.g. `12,90` meaning IDR 12,900 not 12.90) | Implement a `_parse_<currency>_price()` helper that detects the magnitude and normalizes |
| Many product names in a regulator PDF but only `Schedule 1 / Retail` is wanted | Default search picks the first heading occurrence; later "Drum Sale" / "Bulk" sections leak into the parse | Anchor on the *last* `SCHEDULE 1` occurrence and slice text until the next "Drum Sale" / "Bulk" marker |
| API endpoint returns 200 but rows lack a date | Endpoint is rolling-window without timestamps in the payload | Use the request date as `observation_date`, fall back to the page's `Last-Modified` header, or pair the rolling endpoint with a "yearly" endpoint that does carry dates |
| Many rows logged "No COICOP mapping for X — dropping row" | `_COICOP_MAP` doesn't cover an item the source emits | Inspect the missing item; either add to `_COICOP_MAP` (if it really maps cleanly) or accept the drop (if it's an outlier you don't want polluting the basket) |
| Duplicate rows on re-run | `observation_hash` is being computed before all key fields are populated | Move the `make_hash(row, _IDENT)` call to the very end of the row construction, after every `subnational_area` / `city` / `address` / `price_local` field has been set |

After fixing, re-run only the failing source key(s).

### Phase 8 — Report and document

Output a final summary **to chat** (no in-tree artifacts file for now — that decision is deferred until we've run the skill on three countries and seen what teammates actually need):

- **Working sources by `analytical_role`** (retailer_sku / official_avg / tariff / cpi_benchmark / aggregate_proxy): name, country, `source_key` or spider name, row count from the test run, one sample record
- **Skipped sites**: name, URL, reason (use the bucket names from Phase 3 / 3-fetcher so they're consistent and searchable). Include sources that probe-passed but failed Phase 6's ≥5-rows bar — record the row count and a one-line hypothesis
- **Per-country COICOP coverage table** — a 13-row table showing, for each COICOP 2018 division (01–13), which onboarded source(s) cover it, at what cadence, and via which `analytical_role`. Mark `—` for uncovered divisions; this surfaces the next gap to onboard. Distinguish between *price-level coverage* (retailer_sku / official_avg / tariff / aggregate_proxy) and *index coverage* (cpi_benchmark) — both are valuable but feed different layers of PPP analysis.
- Append new blockers to `references/known_blockers.md` so the next run skips them faster — match the existing **blocker-class headings** (Cloudflare strict, AWS WAF, Akamai tenant, Imperva Incapsula, PerimeterX, CDN connection-reset, etc.). One-line entry per site under the heading whose signature matched.
- **Cold-start writeback only:** write `references/inventories/<region>/<country>.md` from the Phase 2 sub-agent's output. If the agent surfaced cross-country aggregators, append them to `references/inventories/<region>/_aggregators.md` (create the file if it doesn't exist).

Then save an engram memory observation (type: `discovery`) titled "Onboarded N price sources for <country>" with the working list, the new blockers, and the COICOP coverage table. The engram observation is the **only** cross-conversation persistence for the onboarding report today — revisit whether to also write an in-tree `_onboarding.md` after the third country.

## Quick reference

- **Source classification axes** (scaffolding × extraction_pattern × analytical_role × coicop_classification): top of this file
- **Spider templates** (3 patterns for scaffolding=spider): `references/spider_templates.md`
- **Fetcher pattern** (contract + helpers + worked examples for scaffolding=fetcher): `references/fetcher_pattern.md`
- **Probe scripts** (curl, Playwright dump, API sniffer, PDF/XLS inspectors): `references/probe_patterns.md`
- **Known blockers** (skip-on-sight list): `references/known_blockers.md`

## Open design questions

These came out of real onboarding runs and are not yet resolved. Surface them with the user when relevant, or treat them as candidates for a future skill revision.

- **Headline CPI has no slot in IndexObservation.** The schema requires `coicop_code` (01–13), but the analyst running PPP / inflation nowcasting wants the *all-items* headline index too. SingStat publishes it as series `1`; we currently drop it because there is no sanctioned sentinel. Options: add `coicop_code: "00"` for all-items, add a separate `series_label` column, or split into a third schema. Until decided, fetchers drop the headline row.

## Residual-source priority (after the first pass)

After the first country onboarding pass lands the easy fetcher wins (REST APIs, public XLSX / PDF dumps), residual deferred sources almost always fall into three buckets:

1. **Cloudflare-protected listing aggregators** (real-estate, classifieds) — needs `scrapy-playwright` + stealth + new `scrapy_listing` template
2. **SPA telco / utility plan pages** (Singtel, StarHub, M1 in SG; equivalents in other markets) — needs `scrapy-playwright`
3. **Akamai-protected SKU retailers** (Cold Storage, NTUC parallel brands) — same Playwright stack as #1, but lower marginal value if FairPrice-class chains are already covered

Prioritise in this order:

- **Gap-COICOPs first**: any source whose COICOP code is not yet covered by the country's already-onboarded set. PropertyGuru-class rental aggregators usually fall here (04.1.1).
- **Redundancy second**, and *only after* the anti-bot template has already been built for a higher-priority site. Cracking Cloudflare/Akamai twice in a row before the first one's template lands is wasted effort — build the template once on the gap-COICOP source, then reuse.

Don't bundle these into a routine country onboarding. Each is its own dedicated effort. Surface them in the Phase 8 report as "Next gaps to target (priority order)" so the next session has a clear queue.

## Anti-patterns to avoid

- Don't invent selectors. If the probe HTML is empty or hydration didn't complete, either fix the probe or skip the site — guessed selectors waste an entire iteration cycle.
- Don't force a fetcher-shaped source into a Scrapy spider. PDFs, Excel files, regulator tariff tables, and CPI publications belong in `src/prices/fetchers/`, not in `spiders/`. Trying to crawl a static stats-office page with Scrapy produces a fragile spider that does what `pd.read_html()` does in three lines.
- Don't put `region:`, `subregion:`, `country:`, or `source:` in YAML manifest bodies. Path-derived; redundant; breaks the loader.
- Don't put `priority:` in YAML. Removed in v4. PPP wants all sources, not a ranking — `analytical_role` already encodes what layer of analysis the source feeds.
- Don't put `source_type:` (A–F letters) in YAML. Removed in v4. Use the four orthogonal axes (`scaffolding`, `extraction_pattern`, `analytical_role`, `coicop_classification`).
- Don't put `observation_level:` in YAML. Removed in v4. Schema choice (PriceObservation vs IndexObservation) is implied by `analytical_role`.
- Don't use `SOURCE_META = [...]` in fetcher modules. One file = one fetcher function = one source. All metadata lives in the YAML manifest; private module-level constants like `_BASE_URL`, `_CURRENCY` are recommended but not required.
- Don't mix PriceObservation and IndexObservation rows in one fetcher. If a source publishes both averaged prices and CPI indexes, write two fetchers.
- Don't emit rows with null `coicop_code` when `coicop_classification ∈ {source_curated, publisher_labeled}`. Log a warning and drop instead — a null where the schema expects a value is pollution masquerading as coverage.
- Don't write a country-bound fetcher when a regional aggregator (`_shared/<region>/`) already covers the country. Add a thin per-country wrapper + a per-country YAML pointing at the shared module instead.
- Don't write per-country YAMLs for truly global aggregate series (oil benchmarks, IMF FX). They live as a single `_global/<source>.yaml` because the rows are global by definition.
- Don't re-do Phase 2 discovery from scratch when `references/inventories/<region>/<country>.md` already exists. The warm-start path is the seed; supplement only for documented gaps. (Outside EAP, the cold-start path is expected — write back the inventory at Phase 8.)
- Don't leave old-schema YAMLs unmigrated when the skill runs on a country. Phase 1 upgrades them in place via inventory lookup — that's how the repo migrates organically.
- Don't add a spider's currency by parsing the price symbol — set it at the spider class level (`currency = "VND"`). Sites that display "$" for Brunei dollars (BND) will be miscoded otherwise. But don't blindly take `countries.yaml` either when the site states its own currency code — see Phase 5A.
- Don't batch multiple countries in one run. Each country has its own retailers, CDNs, stats-office release format, and product URL conventions — the discovery work is what costs time, not the scaffolding.
- Don't treat CPI (`analytical_role: cpi_benchmark`) as a fallback "when nothing else exists for division X." It's the benchmark series that every country needs *in addition to* its price-level sources, because the downstream PPP / inflation-nowcasting analysis compares the two.
- Don't ship a source that probe-passes but returns 0–4 rows in the Phase 6 test. Record it as skipped with a hypothesis; revisit later.
- Don't trust scout sub-agents that say "selectors_unknown: true" — that's a signal to do a real Playwright probe, not to invent selectors anyway.
- Don't try to do COICOP classification in retailer SKU spiders. `src/prices/enrich/classifier/` is the downstream classifier — spiders just emit `product_name` + `category`. Note the classifier consumes the **raw** product name: normalizing or canonicalizing text in the spider measurably *hurts* accuracy, so emit the name exactly as the site renders it.
- Don't route anything to `src/cpi/coicopping/`. That Gemini classifier is retired. A handful of older spider docstrings and YAML `notes:` still name it — they're stale comments, not live wiring.
