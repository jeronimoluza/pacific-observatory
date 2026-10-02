# Source classification — the four axes and the operational fields

Read this at Phase 2.5, when you have candidates to classify. Choosing a *route*
does not need it; the router's 6-line summary is enough for that.

All four axes go into the YAML manifest — full schema in `yaml_schema.md`.

## Axis 1 — `scaffolding` (binary)

| Value | Meaning |
|---|---|
| `spider` | Scrapy spider in `src/prices/price_scraping/spiders/`. Retailer SKU catalogues, real-estate / classifieds listings. |
| `fetcher` | Plain-Python module in `src/prices/fetchers/`. Everything else — official APIs, stats-office downloads, tariff pages, CPI publications. |

Spiders probe with the tier ladder (1A HTML / 1B JSON / 2 Playwright / skip).
Fetchers probe by payload shape.

## Axis 2 — `extraction_pattern`

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

Tells the next run what shape of code lives in the module without re-opening it.
Drives which recipe in `fetcher_pattern.md` applies.

## Axis 3 — `analytical_role`

| Value | Examples | PPP layer |
|---|---|---|
| `retailer_sku` | FairPrice SG, KlikIndomaret ID, Coupang KR | Per-SKU stickiness + basket assembly |
| `official_avg` | SingStat ARP, BPS HK-58, JP Retail Price Survey | Item-level averages for basket |
| `tariff` | SP Group SG, PLN ID, FCCC fuel, Singtel plans | Administered-price layer |
| `cpi_benchmark` | DOSM CPI, PSA CPI, SBS CPI, ABS CPI, BPS CPI | Index benchmark (NOT a fallback for missing price-level coverage) |
| `aggregate_proxy` | **(a)** commodity / FX reference series — WB Pink Sheet, Brent/WTI, IMF FX. **(b)** cost-of-living survey publishers — livingcost, expatistan, mylifeelsewhere, numbeo. | Reference series. **(b) is the larger population by far** — 103 of 302 manifests carry this role and most are survey publishers. They already exist for most countries; never add more, and never count them as coverage. |

Replaces the old `priority` field. Sources of different analytical roles are
**complements**, not substitutes — the PPP analyst wants all roles populated, not
a "best one wins" ranking.

Treating `cpi_benchmark` as a fallback "when nothing else exists for division X"
is a category error. It is the benchmark series every country needs *in addition
to* its price-level sources, because the downstream analysis compares the two.

## Axis 4 — `coicop_classification`

Declares who tags COICOP for the rows this source emits.

| Value | Used for | Handler |
|---|---|---|
| `classifier` | Retailer SKU spiders, stats-office tables with long free-text item lists | `src/prices/enrich/classifier/` — ensemble-embedding → logistic-regression head, run by `prices process --stage classify`. Predicts the COICOP **leaf** from the raw product name. (Renamed 2026-08-05 from `deferred_gemini`, which named a retired Gemini reranker at `src/cpi/coicopping/` — do not route new sources there; that classifier is retired and the older docstrings naming it are stale comments, not live wiring.) |
| `source_curated` | Fuel, electricity, water, telco, real-estate, tariff schedules, restaurant aggregators — sources whose domain unambiguously determines COICOP | Fetcher module carries a `_COICOP_MAP` constant written at onboarding |
| `publisher_labeled` | CPI publications (publisher emits its own COICOP labels) | Fetcher reads the publisher's labels; may need a translation map (e.g. Bahasa → COICOP codes) |

Rows that should carry `coicop_code` but for which the map fails MUST be dropped
with a logged warning. A null `coicop_code` row that should have been populated is
pollution masquerading as coverage.

**Do not do COICOP classification inside a retailer SKU spider.** Spiders emit
`product_name` + `category`. The classifier consumes the **raw** product name —
normalizing or canonicalizing text in the spider measurably *hurts* accuracy, so
emit the name exactly as the site renders it.

## Enrichment-operational fields

The four axes route a source through the pipeline. A *separate* set of YAML fields
is read by the enrichment stage and the build. Populate these explicitly for every
new source; scaffolding is not done until they are set.

| Field | Required? | Author rule | What it drives |
|---|---|---|---|
| `channel` | **required on every manifest — the key must be present even when the value is `null`** | Pick from the closed enum `Channel` in **`src/prices/enrich/schemas.py`** (that module is the authority; `configs/_examples/template.yaml` shows only one example value). Use `null` for non-retail sources where `analytical_role ∈ {cpi_benchmark, official_avg, tariff, aggregate_proxy}`. | Source-mix reporting, per-channel slicing. **Gotcha:** a value outside the enum, or an omitted `channel:` key, raises at load time and takes down the *global* `prices collect --list` — not just that source. Both have happened (a `fresh_market` value; a fetcher YAML with no `channel:`). |
| `coicop_codes` | **required for narrow sources**; omit for wide | A *narrow source* is one whose entire catalog falls under a single COICOP 3-digit class (residential rentals → `04.1`; gasoline retail → `07.2`). Declare every code the source emits. For wide sources (supermarkets, hypermarkets, marketplaces) leave unset — the classifier assigns leaves per product. | Lets `source_curated` / `publisher_labeled` rows carry a code without the classifier; feeds the Phase-8 coverage report |
| `language` | optional, recommended | ISO 639-1 of the dominant product-name language. Falls back to the country's first language in `src/configs/countries.yaml`, then `"en"`. | Tier-a structural regex variants. `_resolve_lang()` returns the *effective* language, not always the official one. |

### Narrowness rule

A source is **narrow** iff `len({c[:4] for c in coicop_codes}) == 1`, where `c[:4]`
is the 3-digit class prefix. `["04.1.1"]` and `["04.1.1", "04.1.2"]` are both narrow.
`["07.2.2", "07.3.2"]` is wide — fuel and transit fares are not substitutable.

> The historical justification was that narrow sources "bypass tier-b and tier-c".
> That cascade was **removed on 2026-07-24** — there is no `tier_b` package and no
> `tier_c.py`. [ADR-0002](../../../docs/adr/0002-source-curated-short-circuit.md)
> and ADR-0003 describe the retired design. The rule survives because declaring a
> known COICOP code beats asking a classifier to rediscover it.

### Worked examples

- **Residential rentals spider** (propertyguru, lamudi, ddproperty): `coicop_codes: ["04.1.1"]` → narrow. Tier-a still extracts `pricing_basis=monthly` from `"RM 2,200 /mo"`. `sub_label_id` stays null.
- **Supermarket** (emart, coles, fairprice): leave `coicop_codes` unset — the catalog spans most of divisions 01–13.
- **Pharmacy chain** (watsons, boots): same. Cache-derived codes pick up the dominant 06.x / 13.x.
- **Fuel retailer**: `coicop_codes: ["07.2.2"]` → narrow.
- **Cost-of-living survey publisher**: not an outlet. `channel: null`, `analytical_role: aggregate_proxy`, `coicop_codes` unset.

For every other source pick the `channel` value whose discriminating test matches,
from the table in `src/prices/docs/GLOSSARY.md`. One list, one place.

These fields are independent of the four axes — a `coicop_classification: source_curated`
spider MUST still set both `channel` AND `coicop_codes`. Routing classification is not
operational codes.

## Retired keys — never write these

`priority:`, `source_type:` (A–F letters), `observation_level:`, `coicop_divisions:`.
All removed in v4. Also never put `region:`, `subregion:`, `country:` or `source:` in a
manifest body — the loader derives them from the path and their presence breaks it.
