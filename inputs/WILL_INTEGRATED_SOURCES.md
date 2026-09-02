# Will's EAP handoff — what was integrated

**Integrated:** 2026-09-01
**Source package:** `inputs/eap_price_scraper_handoff_20260901.zip` (created 2026-09-01 by Will)
**Branch:** `feat/price-sources-jero`

## Summary

Will's package contained **60 validated sources** across **17 countries** (16 EAP Pacific
Islands + 1 EAP East Asia). **56 configs + 52 spider files were integrated**, plus two
modifications to existing spiders. Three configs were deliberately dropped as duplicates.

His row counts were independently audited before integration: **all 60 claimed row counts
matched the JSONL/CSV evidence shipped in `validation/latest_outputs/`. Zero mismatches,
zero missing evidence files, zero sources below the 5-row bar.** This package is
evidence-first and its numbers can be trusted.

## Coverage effect (bar = >=5 sources AND >=2 food)

His work **closed 7 countries** that were previously failing:

| Country | Before | After | Owner per workbook |
|---|---|---|---|
| french_polynesia | 2src/1food | 5src/2food | Will |
| nauru | 2src/2food | 5src/3food | Will |
| palau | 2src/1food | 5src/2food | Will |
| papua_new_guinea | 3src/1food | 6src/2food | Will |
| **marshall_islands** | **0src/0food** | **6src/3food** | **Jero** |
| **new_caledonia** | 1src/0food | 5src/2food | **Jero** |
| **northern_mariana_islands** | 2src/1food | 5src/2food | **Jero** |

Already passing, further strengthened: fiji (9/6), micronesia_fed_sts (9/5), samoa (10/7),
tonga (12/7), vanuatu (9/2).

**Still short after integration:**

| Country | State | Remaining need | Owner |
|---|---|---|---|
| american_samoa | 5src/0food | 2 food | Will |
| kiribati | 5src/0food | 2 food | Jero |
| tuvalu | 5src/1food | 1 food | Jero |
| korea_dem_peoples_rep | 2src/0food | 3 src + 2 food | Will |

EAP Pacific + DPRK: **12 of 16 now pass.** Global countries at the bar: **136**.

## IMPORTANT: ownership

**Only 22 of his 60 sources were in his own countries.** 37 were in Jero-owned countries
(fiji, kiribati, marshall_islands, micronesia_fed_sts, new_caledonia,
northern_mariana_islands, tonga, tuvalu) and 1 was DPRK. He worked the whole EAP Pacific
regardless of the Jero/Will split in the pending workbooks.

Practical consequence: **Jero's remaining pending list dropped from 21 countries to 18**,
and two more got much cheaper — kiribati went from 4 builds to 2 (food only), tuvalu from
3 to 1. A New Caledonia agent had already been dispatched in wave 9 and was stopped as
redundant once this package was reviewed.

Note his triage targets **10 sources per country**, not our 5, so his
`docs/COVERAGE_AND_PRIORITY.md` "under-covered" list is NOT our failing list.

## Changes made during integration (3 fixes)

### 1. `o4a2_to.py` — kept OUR version, ported his 6 vendor subclasses onto it

His overlay version would have **overwritten our existing spider and reverted a fix we
already shipped.** Our version strips the `PICK UP FROM <STORE>` boilerplate that O4A2
appends to every product title; his did not, and his own evidence proves it — all 250 rows
of his `o4a2_hihifo_supermarket_to` sample read like
`Box of Chicken (Puha Moa) 15Kg - PICK UP FROM HIHIFO SUPERMARKET, FO'UI"`. That text would
have gone straight into the COICOP classifier, which reads `product_name`.

Resolution: kept our `O4a2ToSpider` (boilerplate strip + `vendor_filter`) and appended his
6 non-duplicate vendor subclasses, which now inherit the strip via `PRODUCTS_PATH`
collection selection. **Verified after integration: `o4a2_zf_company_to` emits 250 rows
with 0 names carrying the boilerplate.**

### 2. Dropped 3 Tonga configs as duplicate shelves

- `o4a2_hihifo_supermarket_to.yaml` — duplicate of existing `hihifo_supermarket_to.yaml`
- `o4a2_golden_star_to.yaml` — duplicate of existing `golden_star_to.yaml`
- `o4a2_to.yaml` — blended all-vendor marketplace; would have counted every vendor a
  second (and Hihifo/Golden Star a third) time

The existing two use `spider: o4a2_to` with a `vendor_filter` in `spider_kwargs`. Same
shelves, different filenames — a filename-only duplicate check does not catch this.

### 3. Normalised `analytical_role: marketplace_sku` -> `retailer_sku` on 8 configs

`marketplace_sku` is not one of the five valid roles
(`retailer_sku, official_avg, tariff, cpi_benchmark, aggregate_proxy`). `config.py` types
the field as bare `str | None` so it does not raise, but it silently breaks role-based
filtering and reporting. Affected: `o4a2_atlas_liquor_to`, `o4a2_go_gas_to`,
`o4a2_hot_pizza_to`, `o4a2_juice_lab_to`, `o4a2_tropical_taste_to`, `o4a2_zf_company_to`,
`pngmart_pg`, `wikonomi_pg`.

Also carried in from his overlay: **`food_pro.py` currency `"K"` -> `"PGK"`** — a genuine
bug fix on an existing PNG source (ISO 4217 code, not the display symbol).

## OPEN CAVEATS — not fixed, need a decision

### A. All 10 Tonga sources price in NZD/AUD, never TOP

Tonga's currency is TOP (paʻanga). Will's Tonga sources declare NZD (9) and AUD (1).
This is not obviously an error: O4A2 is a **diaspora pickup/gift platform** — NZ-based
buyers order online and family collects in Tonga — and our existing `o4a2_to` docstring
already documents that. Shopify returns NZD explicitly, and per skill doctrine we take what
the site returns.

**But these are not domestic Tongan shelf prices.** They embed NZ retail margins,
remittance markup and FX. Tonga now reads 12src/7food, and 6 of those food sources are this
platform. Treat Tonga's food coverage as diaspora-priced, not comparable to a domestic
shelf, until someone decides how PPP should handle it. `pokosshop_to` in AUD is a separate
storefront and was not separately verified.

### B. 24 non-retail sources are spiders, not fetchers

22 `tariff` and 2 `official_avg` sources are implemented as Scrapy spiders emitting
`raw_items/*.jsonl`, rather than fetchers emitting PriceObservation / IndexObservation CSVs.
They work and they produced rows, but this diverges from the skill's convention
("don't force a fetcher-shaped source into a Scrapy spider") and it means the
`coicop_classification: source_curated` COICOP maps **never run** for them — those rows go
through the classifier instead. `asiapress_kp_market` (official_avg + source_curated) is
the clearest instance.

### C. Same-host breadth is not independent breadth

Will flags this himself and it is worth preserving: Tonga's count is driven by O4A2
vendor-level feeds on one host, and Samoa's partly by MySamoa/Shopify merchants on one host.
Nine Tonga sources share `o4a2.com`. Counting them as nine independent sources overstates
resilience — if that host changes, nine sources fail together.

## His recorded non-successes (do not re-probe)

From `probes/candidate_outcomes.csv`:

- Hiki Tonga official: Cloudflare/DNS error 1001. Shop.app mirror: 429.
- M&F Market Guam: Shopify reports shop unavailable.
- Rainbow Enterprise Nauru: empty reply / parked-page response.
- Carrefour French Polynesia (Punaauia, Arue): country-access 403 from his environment;
  guessed API returned 401. **Worth retrying from a different geography** — this is the
  single best remaining French Polynesia food lead.
- Lollipop Tahiti: is WooCommerce, but adult/lingerie catalogue with only incidental
  sweets. Rejected on relevance, not on access.
- PNG S4G / Lae Market: low-yield, noisy TakeApp probes, not promoted.
- PNG POM Online Groceries: root and category probes exposed zero products.
- PNG `take.app/na2oxtrading`: **pending, not built.** His probe found 16 PGK-priced
  physical products. This is his recommended next PNG addition.

## Verification performed at integration

- `po prices collect --list` exits 0 (a bad `channel:` value breaks the loader globally).
- All 56 configs resolve to an existing spider name.
- Live re-runs: `o4a2_zf_company_to` 250 rows / 0 boilerplate names,
  `o4a2_go_gas_to` 6 rows, `nutrigo_nc` 31 rows.
- `food_pro.py` diff confirmed to be the single currency line and nothing else.

## Not integrated

`validation/`, `probes/`, and `docs/` from his package were read but not copied into the
tree. They remain inside `inputs/eap_price_scraper_handoff_20260901.zip` if needed —
`probes/candidate_outcomes.csv` is the one worth re-reading before any new EAP Pacific
discovery pass.

His inventory writebacks were NOT included in the package, so
`.claude/skills/onboard-price-sources/references/inventories/eap/*.md` still do not record
any of the dead ends listed above. **Someone should port that `candidate_outcomes.csv` into
the per-country inventory files**, or the next discovery run will re-probe Carrefour PF,
M&F Guam and Rainbow Nauru from scratch.
